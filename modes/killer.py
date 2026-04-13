"""
Killer – Gran Darts rules.
Assignment phase: each player throws one dart with off hand to claim a number.
Re-throw if bullseye or already taken.
Game phase: earn Life on your number to become Killer, then eliminate opponents.
Last player standing wins.
"""
import random
from modes.base import BaseMode

BOARD_ORDER = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]


def _adjacent(n):
    if n not in BOARD_ORDER:
        return set()
    i = BOARD_ORDER.index(n)
    return {BOARD_ORDER[(i - 1) % 20], BOARD_ORDER[(i + 1) % 20]}


RING_HITS = {"single": 1, "outer_single": 1, "inner_single": 1, "double": 2, "triple": 3, "bull": 0, "bullseye": 0, "miss": 0}


class KillerMode(BaseMode):
    mode_id = "killer"
    mode_name = "Killer"
    description = "Claim your number with your off hand, earn Life to become a Killer, then eliminate opponents."
    options_schema = {
        "only_double":      {"type": "boolean", "default": False, "description": "Only double hits count after target selection"},
        "only_triple":      {"type": "boolean", "default": False, "description": "Only triple hits count after target selection"},
        "straight_off":     {"type": "boolean", "default": False, "description": "All players start already in Killer state"},
        "one_hit_killer":   {"type": "boolean", "default": False, "description": "All players start with full Life (3)"},
        "no_life_recovery": {"type": "boolean", "default": False, "description": "Hitting own number does not restore Life"},
        "easy_players":     {"type": "string",  "default": "",    "description": "Comma-separated player positions for easy mode e.g. '1,3'"},
        "max_rounds":       {"type": "integer", "default": 0, "min": 0, "max": 50,
                             "description": "Max rounds (0 = unlimited). First 50% normal, next 30% double, final 20% triple."},
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.starting_lives   = 3
        self.only_double      = options.get("only_double", False)
        self.only_triple      = options.get("only_triple", False)
        self.straight_off     = options.get("straight_off", False)
        self.one_hit_killer   = options.get("one_hit_killer", False)
        self.no_life_recovery = options.get("no_life_recovery", False)
        self.max_rounds       = max(0, int(options.get("max_rounds", 0)))

        # Round tracking (only meaningful when max_rounds > 0)
        self._current_round = 0
        self._last_multiplier = 1

        easy_str = options.get("easy_players", "").strip()
        if easy_str:
            try:
                easy_indices = {int(x.strip()) - 1 for x in easy_str.split(",")}
                self._easy = {p["id"]: (i in easy_indices) for i, p in enumerate(players)}
            except Exception:
                self._easy = {p["id"]: False for p in players}
        else:
            self._easy = {p["id"]: False for p in players}

        # Assignment phase state
        self._phase = "assignment"           # "assignment" | "game"
        self._number = {}                    # pid → assigned number
        self._number_to_player = {}          # number → pid
        self._assignment_order = [p["id"] for p in players]  # who still needs to assign

        # Game phase state
        if self.straight_off or self.one_hit_killer:
            self._lives     = {p["id"]: self.starting_lives for p in players}
            self._is_killer = {p["id"]: True  for p in players}
        else:
            self._lives     = {p["id"]: 0     for p in players}
            self._is_killer = {p["id"]: False for p in players}

        self._eliminated       = {p["id"]: False for p in players}
        self._elimination_order = []

    # ── helpers ───────────────────────────────────────────────────────────────

    def _ring_hits(self, ring):
        """Return base hit value: single=1, double=2, triple=3, else 0."""
        if ring in ('single', 'outer_single', 'inner_single'):
            base = 1
        elif ring == 'double':
            base = 2
        elif ring == 'triple':
            base = 3
        else:
                return 0  # bull, bullseye, miss
        if self.only_double and ring != 'double': return 0
        if self.only_triple and ring != 'triple': return 0
        return base

    def _hit_multiplier(self):
        """Return 1/2/3 based on which phase of max_rounds we're in."""
        if self.max_rounds <= 0:
            return 1
        r = self._current_round
        double_start = int(self.max_rounds * 0.50)
        triple_start = int(self.max_rounds * 0.80)
        if r >= triple_start:
            return 3
        if r >= double_start:
            return 2
        return 1

    def on_turn_start(self, state):
        if self._phase == "game" and self.max_rounds > 0:
            # Track rounds: increment when first alive player starts their turn
            first_alive_idx = next(
                (i for i, p in enumerate(state["players"])
                 if not self._eliminated.get(p["id"], False)),
                None
            )
            if first_alive_idx is not None and state["current_player_idx"] == first_alive_idx:
                self._current_round += 1
        # Announce when multiplier changes
        new_mult = self._hit_multiplier()
        if new_mult != self._last_multiplier:
            self._last_multiplier = new_mult
            if new_mult == 2:
                state['_pending_announcement'] = "🔥 DOUBLE DAMAGE! All hits count double this round!"
            elif new_mult == 3:
                state['_pending_announcement'] = "💥 TRIPLE DAMAGE! All hits count triple — anything goes!"

    def _hits_segment(self, pid, segment):
        my_num = self._number.get(pid)
        if my_num is None: return False
        if segment == my_num: return True
        if self._easy[pid] and segment in _adjacent(my_num): return True
        return False

    def _attack_target(self, attacker_pid, segment):
        if segment in self._number_to_player:
            return self._number_to_player[segment]
        if self._easy[attacker_pid]:
            for num, pid in self._number_to_player.items():
                if segment in _adjacent(num):
                    return pid
        return None

    # ── scoring ───────────────────────────────────────────────────────────────

    def initial_scores(self):
        return {p["id"]: self._lives[p["id"]] for p in self.players}

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        scores = dict(state["player_scores"])

        # ── Assignment phase ──────────────────────────────────────────────────
        if self._phase == "assignment":
            # Must be this player's assignment turn
            if not self._assignment_order or self._assignment_order[0] != pid:
                return {"player_scores": scores, "scored": 0,
                        "message": "Wait your turn for number assignment"}

            # Reject bullseye / miss
            if ring in ("bull", "bullseye", "miss") or segment == 0:
                return {"player_scores": scores, "scored": 0,
                        "advance_turn": False,
                        "message": f"Bullseye/miss — throw again!",
                        "announcement": f"{player['name']} hit bullseye — throw again with your off hand!"}

            # Reject already taken
            if segment in self._number_to_player:
                taken_by = next(p["name"] for p in self.players
                                if p["id"] == self._number_to_player[segment])
                return {"player_scores": scores, "scored": 0,
                        "advance_turn": False,
                        "message": f"{segment} is taken by {taken_by} — throw again!",
                        "announcement": f"❌ {segment} is already taken by {taken_by}! {player['name']}, throw again."}

            # Valid — assign the number
            self._number[pid] = segment
            self._number_to_player[segment] = pid
            self._assignment_order.pop(0)

            ann = f"{player['name']} claims number {segment}!"

            # Check if all assigned
            if not self._assignment_order:
                self._phase = "game"
                ann += " All numbers assigned — game on!"

            return {"player_scores": scores, "scored": 0,
                    "advance_turn": True,
                    "message": ann, "announcement": ann}

        # ── Game phase ────────────────────────────────────────────────────────
        if self._eliminated[pid]:
            return {"player_scores": scores, "scored": 0,
                    "message": f"{player['name']} is eliminated"}

        hits = self._ring_hits(ring)
        mult = self._hit_multiplier()
        if hits > 0:
            hits = hits * mult

        # Pick up any pending round-change announcement (set in on_turn_start)
        pending_ann = state.pop('_pending_announcement', None)

        # Phase 1: earning Life
        if not self._is_killer[pid]:
            if self._hits_segment(pid, segment) and hits > 0:
                self._lives[pid] = min(self.starting_lives, self._lives[pid] + hits)
                scores[pid] = self._lives[pid]
                if self._lives[pid] >= self.starting_lives:
                    self._is_killer[pid] = True
                    ann = pending_ann or f"💀 {player['name']} is now a KILLER! Watch out!"
                    return {"player_scores": scores, "scored": 0,
                            "message": f"{player['name']} is now a KILLER!",
                            "announcement": ann}
                ann = pending_ann or f"{player['name']} — {self._lives[pid]}/{self.starting_lives} Life (+{hits})"
                return {"player_scores": scores, "scored": 0,
                        "message": f"Life: {self._lives[pid]}/{self.starting_lives} (+{hits})",
                        "announcement": ann}
            ann = pending_ann  # show round announcement even on a miss
            return {"player_scores": scores, "scored": 0,
                    "message": f"Need Life on {self._number.get(pid, '?')} ({self._lives[pid]}/{self.starting_lives})",
                    "announcement": ann}

        # Phase 2: Killer attacking
        target_id = self._attack_target(pid, segment)
        if target_id is None:
            return {"player_scores": scores, "scored": 0, "message": "No target hit",
                    "announcement": pending_ann}

        if target_id == pid:
            if not self.no_life_recovery and hits > 0:
                self._lives[pid] = max(0, self._lives[pid] - hits)
                scores[pid] = self._lives[pid]
                if self._lives[pid] < self.starting_lives:
                    self._is_killer[pid] = False
                if self._lives[pid] == 0:
                    self._eliminated[pid] = True
                return {"player_scores": scores, "scored": 0,
                        "message": f"Self-hit! {player['name']} loses {hits} Life ({self._lives[pid]} left)",
                        "announcement": pending_ann or f"Oops! {player['name']} hit their own number!"}
            return {"player_scores": scores, "scored": 0, "message": "Self-hit (no effect)",
                    "announcement": pending_ann}

        target_player = next(p for p in self.players if p["id"] == target_id)
        if self._eliminated[target_id]:
            return {"player_scores": scores, "scored": 0,
                    "message": f"{target_player['name']} already eliminated",
                    "announcement": pending_ann}
        if hits == 0:
            return {"player_scores": scores, "scored": 0, "message": "No effect (wrong ring type)",
                    "announcement": pending_ann}

        prev_lives = self._lives[target_id]
        new_lives  = max(0, prev_lives - hits)
        self._lives[target_id] = new_lives
        scores[target_id] = new_lives

        if prev_lives == 0 or hits > prev_lives:
            self._lives[target_id] = 0
            scores[target_id] = 0
            self._is_killer[target_id] = False
            self._eliminated[target_id] = True
            if target_id not in self._elimination_order:
                self._elimination_order.append(target_id)
            msg = f"💀 {target_player['name']} is ELIMINATED!"
        elif new_lives == 0:
            if self._is_killer[target_id]:
                self._is_killer[target_id] = False
            msg = f"{target_player['name']} hits 0 Life! One more hit eliminates them!"
        else:
            if self._is_killer[target_id] and new_lives < self.starting_lives:
                self._is_killer[target_id] = False
                msg = f"{target_player['name']} loses {hits} Life and Killer status! ({new_lives} left)"
            else:
                msg = f"{target_player['name']} loses {hits} Life! ({new_lives} left)"

        return {"player_scores": scores, "scored": hits,
                "message": msg, "announcement": pending_ann or msg}

    def is_player_eliminated(self, pid):
        return self._eliminated.get(pid, False)

    def is_game_over(self, state):
        alive = [pid for pid, elim in self._eliminated.items() if not elim]
        if len(alive) == 1:
            state["winner_id"] = alive[0]
            return True
        # Round limit reached
        if self.max_rounds > 0 and self._current_round > self.max_rounds:
            # Winner = most lives among alive players
            best = max(alive, key=lambda pid: self._lives[pid])
            state["winner_id"] = best
            return True
        return False

    def get_display_state(self, state):
        return {
            "phase": self._phase,
            "assignment_queue": list(self._assignment_order),
            "lives": self._lives,
            "is_killer": self._is_killer,
            "assigned_numbers": self._number,
            "starting_lives": self.starting_lives,
            "easy_mode": self._easy,
            "eliminated": self._eliminated,
            "elimination_order": self._elimination_order,
            "max_rounds": self.max_rounds,
            "current_round": self._current_round,
            "hit_multiplier": self._hit_multiplier(),
        }

    def restore_state(self, state):
        scores = state.get("player_scores", {})
        self._lives = dict(scores)
        self._is_killer = {p["id"]: self._lives.get(p["id"], 0) >= self.starting_lives
                           for p in state["players"]}
        self._eliminated = {p["id"]: self._lives.get(p["id"], 0) <= 0
                            for p in state["players"]}


MODE_CLASS = KillerMode
