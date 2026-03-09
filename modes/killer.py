"""
Killer – Gran Darts rules.
Each player throws to claim a target number, then hits it to earn Life.
3 Life = become a Killer. Killers attack opponents' numbers to drain their Life.
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


RING_HITS = {"single": 1, "double": 2, "triple": 3, "bull": 0, "bullseye": 0, "miss": 0}


class KillerMode(BaseMode):
    mode_id = "killer"
    mode_name = "Killer"
    description = "Earn Life on your number to become a Killer, then eliminate opponents."
    options_schema = {
        "only_double": {"type": "boolean", "default": False,
                        "description": "Only double hits count after target selection"},
        "only_triple": {"type": "boolean", "default": False,
                        "description": "Only triple hits count after target selection"},
        "straight_off": {"type": "boolean", "default": False,
                         "description": "All players start already in Killer state"},
        "one_hit_killer": {"type": "boolean", "default": False,
                           "description": "All players start with full Life (3)"},
        "no_life_recovery": {"type": "boolean", "default": False,
                             "description": "Hitting own number does not restore Life (requires Straight Off or One Hit Killer)"},
        "easy_players": {"type": "string", "default": "",
                         "description": "Comma-separated player positions for easy mode (adjacent hits count) e.g. '1,3'"},
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.starting_lives = 3  # always 3 per Gran Darts rules

        self.only_double    = options.get("only_double", False)
        self.only_triple    = options.get("only_triple", False)
        self.straight_off   = options.get("straight_off", False)
        self.one_hit_killer = options.get("one_hit_killer", False)
        self.no_life_recovery = options.get("no_life_recovery", False)

        # Per-player easy mode
        easy_str = options.get("easy_players", "").strip()
        if easy_str:
            try:
                easy_indices = {int(x.strip()) - 1 for x in easy_str.split(",")}
                self._easy = {p["id"]: (i in easy_indices) for i, p in enumerate(players)}
            except Exception:
                self._easy = {p["id"]: False for p in players}
        else:
            self._easy = {p["id"]: False for p in players}

        # Life points (0–3+)
        if self.straight_off or self.one_hit_killer:
            self._lives = {p["id"]: self.starting_lives for p in players}
        else:
            self._lives = {p["id"]: 0 for p in players}

        # Killer status
        if self.straight_off or self.one_hit_killer:
            self._is_killer = {p["id"]: True for p in players}
        else:
            self._is_killer = {p["id"]: False for p in players}

        # Number assignment
        easy_pids = {p["id"] for p in players if self._easy.get(p["id"])}
        self._number = self._assign_numbers(players, easy_pids)
        self._number_to_player = {v: k for k, v in self._number.items()}

        # Eliminated set (reached 0 AND got hit once more)
        self._eliminated = {p["id"]: False for p in players}
        self._elimination_order = []  # first out = index 0

    def _assign_numbers(self, players, easy_pids):
        import random as _r
        from itertools import combinations

        def board_dist(a, b):
            ia, ib = BOARD_ORDER.index(a), BOARD_ORDER.index(b)
            return min(abs(ia - ib), 20 - abs(ia - ib))

        easy_players  = [p for p in players if p["id"] in easy_pids]
        normal_players = [p for p in players if p["id"] not in easy_pids]
        n_easy = len(easy_players)
        all_nums = list(range(1, 21))

        if n_easy == 0:
            nums = _r.sample(all_nums, len(players))
            return {p["id"]: nums[i] for i, p in enumerate(players)}

        valid_combos = [c for c in combinations(all_nums, n_easy)
                        if all(board_dist(c[i], c[j]) >= 3
                               for i in range(n_easy) for j in range(i+1, n_easy))]
        if not valid_combos:
            nums = _r.sample(all_nums, len(players))
            return {p["id"]: nums[i] for i, p in enumerate(players)}

        easy_nums = list(_r.choice(valid_combos))
        _r.shuffle(easy_nums)

        forbidden = set()
        for en in easy_nums:
            idx = BOARD_ORDER.index(en)
            forbidden |= {en, BOARD_ORDER[(idx-1)%20], BOARD_ORDER[(idx+1)%20]}

        safe = [n for n in all_nums if n not in forbidden]
        if len(safe) < len(normal_players):
            nums = _r.sample(all_nums, len(players))
            return {p["id"]: nums[i] for i, p in enumerate(players)}

        _r.shuffle(safe)
        assignment = {}
        for i, p in enumerate(easy_players):
            assignment[p["id"]] = easy_nums[i]
        for i, p in enumerate(normal_players):
            assignment[p["id"]] = safe[i]
        return assignment

    def initial_scores(self):
        return {p["id"]: self._lives[p["id"]] for p in self.players}

    def _ring_hits(self, ring):
        """Life change value for a ring, respecting only_double / only_triple options."""
        if self.only_double and ring != "double":
            return 0
        if self.only_triple and ring != "triple":
            return 0
        return RING_HITS.get(ring, 0)

    def _hits_segment(self, pid, segment):
        my_num = self._number[pid]
        if segment == my_num:
            return True
        if self._easy[pid] and segment in _adjacent(my_num):
            return True
        return False

    def _attack_target(self, attacker_pid, segment):
        if segment in self._number_to_player:
            return self._number_to_player[segment]
        if self._easy[attacker_pid]:
            for num, pid in self._number_to_player.items():
                if segment in _adjacent(num):
                    return pid
        return None

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        scores = dict(state["player_scores"])

        if self._eliminated[pid]:
            return {"player_scores": scores, "scored": 0, "message": f"{player['name']} is eliminated"}

        hits = self._ring_hits(ring)

        # ── Phase 1: earning Life to become Killer ────────────────────────────
        if not self._is_killer[pid]:
            if self._hits_segment(pid, segment) and hits > 0:
                self._lives[pid] = min(self.starting_lives + hits, self._lives[pid] + hits)
                # Cap at starting_lives for display purposes (Gran Darts caps at 3)
                self._lives[pid] = min(self._lives[pid], self.starting_lives)
                scores[pid] = self._lives[pid]
                if self._lives[pid] >= self.starting_lives:
                    self._is_killer[pid] = True
                    return {
                        "player_scores": scores, "scored": 0,
                        "message": f"{player['name']} is now a KILLER!",
                        "announcement": f"{player['name']} is now a Killer! Watch out!",
                    }
                return {
                    "player_scores": scores, "scored": 0,
                    "message": f"Life: {self._lives[pid]}/{self.starting_lives}",
                    "announcement": f"{player['name']} — {self._lives[pid]}/{self.starting_lives} Life",
                }
            return {
                "player_scores": scores, "scored": 0,
                "message": f"Need Life on {self._number[pid]} ({self._lives[pid]}/{self.starting_lives})",
            }

        # ── Phase 2: Killer attacking ─────────────────────────────────────────
        target_id = self._attack_target(pid, segment)

        if target_id is None:
            return {"player_scores": scores, "scored": 0, "message": "No target hit"}

        # Self-hit penalty
        if target_id == pid:
            if not self.no_life_recovery and hits > 0:
                # Hitting own number as killer: lose life
                self._lives[pid] = max(0, self._lives[pid] - hits)
                scores[pid] = self._lives[pid]
                if self._lives[pid] < self.starting_lives:
                    self._is_killer[pid] = False  # lose Killer status
                if self._lives[pid] == 0:
                    self._eliminated[pid] = True
                return {
                    "player_scores": scores, "scored": 0,
                    "message": f"Self-hit! {player['name']} loses {hits} Life ({self._lives[pid]} left)",
                    "announcement": f"Oops! {player['name']} hit their own number and loses Killer status!",
                }
            return {"player_scores": scores, "scored": 0, "message": "Self-hit (no effect)"}

        target_player = next(p for p in self.players if p["id"] == target_id)

        if self._eliminated[target_id]:
            return {"player_scores": scores, "scored": 0, "message": f"{target_player['name']} already eliminated"}

        if hits == 0:
            return {"player_scores": scores, "scored": 0, "message": "No effect (wrong ring type)"}

        # Attack target
        prev_lives = self._lives[target_id]
        new_lives = max(0, prev_lives - hits)
        self._lives[target_id] = new_lives
        scores[target_id] = new_lives

        # Dead if already at 0, or if hits would take them below 0 (past -1)
        if prev_lives == 0 or hits > prev_lives:
            self._lives[target_id] = 0
            scores[target_id] = 0
            self._is_killer[target_id] = False
            self._eliminated[target_id] = True
            if target_id not in self._elimination_order:
                self._elimination_order.append(target_id)
            msg = f"{target_player['name']} is ELIMINATED!"
            announcement = msg
        elif new_lives == 0:
            # Reach exactly 0 — lose killer status but not yet eliminated
            if self._is_killer[target_id]:
                self._is_killer[target_id] = False
            msg = f"{target_player['name']} hits 0 Life! One more hit eliminates them!"
            announcement = msg
        else:
            # Target loses killer status if their life drops below starting
            if self._is_killer[target_id] and new_lives < self.starting_lives:
                self._is_killer[target_id] = False
                msg = f"{target_player['name']} loses {hits} Life and Killer status! ({new_lives} left)"
            else:
                msg = f"{target_player['name']} loses {hits} Life! ({new_lives} left)"
            announcement = msg

        return {"player_scores": scores, "scored": hits, "message": msg, "announcement": announcement}

    def is_player_eliminated(self, pid):
        return self._eliminated.get(pid, False)

    def is_game_over(self, state):
        alive = [pid for pid, elim in self._eliminated.items() if not elim]
        if len(alive) == 1:
            state["winner_id"] = alive[0]
            return True
        return False

    def get_display_state(self, state):
        return {
            "lives": self._lives,
            "is_killer": self._is_killer,
            "assigned_numbers": self._number,
            "starting_lives": self.starting_lives,
            "easy_mode": self._easy,
            "eliminated": self._eliminated,
            "elimination_order": self._elimination_order,
        }

    def restore_state(self, state):
        scores = state.get("player_scores", {})
        self._lives = dict(scores)
        self._is_killer = {p["id"]: self._lives.get(p["id"], 0) >= self.starting_lives
                           for p in state["players"]}
        self._eliminated = {p["id"]: self._lives.get(p["id"], 0) <= 0
                            for p in state["players"]}


MODE_CLASS = KillerMode
