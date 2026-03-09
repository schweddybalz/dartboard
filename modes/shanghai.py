"""
Shanghai – 7 rounds, each targeting a number. Highest score wins.
Shanghai (S+D+T in one turn) = instant win.
Easy mode: adjacent numbers score face value (configurable per player).
"""
from modes.base import BaseMode

BOARD_ORDER = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

def _adjacent(n):
    if n not in BOARD_ORDER:
        return set()
    i = BOARD_ORDER.index(n)
    return {BOARD_ORDER[(i - 1) % 20], BOARD_ORDER[(i + 1) % 20]}


class ShanghaiMode(BaseMode):
    mode_id = "shanghai"
    mode_name = "Shanghai"
    description = "7 rounds targeting 1–7. Highest score wins. S+D+T in one turn = instant win."
    options_schema = {
        "rounds": {"type": "integer", "default": 7, "min": 3, "max": 20},
        "easy_mode": {"type": "boolean", "default": False,
                      "description": "Adjacent numbers score face value (no double/triple bonus)"},
        "easy_players": {"type": "string", "default": "",
                         "description": "Comma-separated player positions for easy mode (e.g. '1,3'). Empty = all or none."},
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.total_rounds = options.get("rounds", 7)
        global_easy = options.get("easy_mode", False)
        easy_str = options.get("easy_players", "").strip()
        if easy_str:
            try:
                easy_indices = {int(x.strip()) - 1 for x in easy_str.split(",")}
                self._easy = {p["id"]: (i in easy_indices) for i, p in enumerate(players)}
            except Exception:
                self._easy = {p["id"]: global_easy for p in players}
        else:
            self._easy = {p["id"]: global_easy for p in players}

        self._round_hits = {p["id"]: set() for p in players}
        self._instant_win = False

    def _current_target(self, state) -> int:
        n = len(self.players)
        # turn_number is 1-based; round = ceil(turn / players)
        round_num = (state["turn_number"] - 1) // n + 1
        return min(round_num, self.total_rounds)

    def initial_scores(self):
        return {p["id"]: 0 for p in self.players}

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        target = self._current_target(state)
        scores = dict(state["player_scores"])

        if ring == "miss":
            return {"player_scores": scores, "scored": 0, "message": f"Miss — target is {target}"}

        # Direct hit on target
        if segment == target:
            scored = raw_score
            scores[pid] += scored
            self._round_hits[pid].add(ring)

            is_shanghai = {"single", "double", "triple"}.issubset(self._round_hits[pid])
            if is_shanghai:
                self._instant_win = True
                return {
                    "player_scores": scores,
                    "scored": scored,
                    "winner_id": pid,
                    "advance_turn": True,
                    "announcement": f"SHANGHAI! {player['name']} wins instantly!",
                    "message": "SHANGHAI! Instant win!",
                }
            return {
                "player_scores": scores,
                "scored": scored,
                "message": f"+{scored} on {target}",
                "announcement": f"{player['name']} hits {ring} {target} for {scored}!",
            }

        # Easy mode: adjacent number scores face value
        if self._easy[pid] and segment in _adjacent(target):
            scored = target  # face value of the target, not the adjacent number
            scores[pid] += scored
            return {
                "player_scores": scores,
                "scored": scored,
                "message": f"+{scored} (adjacent {segment} → {target})",
                "announcement": f"{player['name']} hits adjacent {segment}, scores {scored}",
            }

        return {"player_scores": scores, "scored": 0, "message": f"Miss — target is {target}"}

    def is_game_over(self, state):
        if self._instant_win:
            return True
        players_per_round = len(self.players)
        total_turns = self.total_rounds * players_per_round
        return state["turn_number"] > total_turns

    def get_display_state(self, state):
        target = self._current_target(state)
        return {
            "current_target": target,
            "total_rounds": self.total_rounds,
            "round_hits": {pid: list(hits) for pid, hits in self._round_hits.items()},
            "scores": state["player_scores"],
            "easy_mode": self._easy,
        }

    def on_turn_start(self, state):
        pid = state["players"][state["current_player_idx"]]["id"]
        self._round_hits[pid] = set()

    def restore_state(self, state):
        self._instant_win = state.get("game_over", False)
        self._round_hits = {p["id"]: set() for p in state["players"]}


MODE_CLASS = ShanghaiMode
