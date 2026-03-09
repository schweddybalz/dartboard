"""
Around the Clock – Hit 1 through 20 in sequence. First to 20 wins.
Options: must_double_finish (must hit D20 to win), include_bull (21st target is bull).
"""
from modes.base import BaseMode


class AroundTheClockMode(BaseMode):
    mode_id = "around_the_clock"
    mode_name = "Around the Clock"
    description = "Hit 1 through 20 in order. First player to complete the sequence wins."
    options_schema = {
        "include_bull": {"type": "boolean", "default": False,
                         "description": "After 20, must hit bullseye to win"},
        "doubles_skip": {"type": "boolean", "default": False,
                         "description": "A double advances two numbers"},
        "triples_skip": {"type": "boolean", "default": False,
                         "description": "A triple advances three numbers"},
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.include_bull = options.get("include_bull", False)
        self.doubles_skip = options.get("doubles_skip", False)
        self.triples_skip = options.get("triples_skip", False)
        self._target = {p["id"]: 1 for p in players}

    def initial_scores(self):
        # score = current target number (progress indicator)
        return {p["id"]: 1 for p in self.players}

    def _max_target(self):
        return 25 if self.include_bull else 20

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        target = self._target[pid]
        scores = dict(state["player_scores"])

        hit = False
        advance = 1

        if self.include_bull and target == 25:
            hit = ring in ("bull", "bullseye")
        else:
            hit = segment == target and ring != "miss"

        if not hit:
            return {
                "player_scores": scores,
                "scored": 0,
                "message": f"Need {target}",
            }

        # Determine how many to advance
        if ring == "double" and self.doubles_skip:
            advance = 2
        elif ring == "triple" and self.triples_skip:
            advance = 3

        new_target = target + advance
        # Cap at max — don't skip past the finish line, just reach it
        max_t = self._max_target()
        if new_target > max_t:
            new_target = max_t + 1  # triggers win below
        self._target[pid] = new_target
        scores[pid] = new_target

        if new_target > max_t:
            # Player finished!
            return {
                "player_scores": scores,
                "scored": 1,
                "winner_id": pid,
                "advance_turn": True,
                "message": f"{player['name']} wins!",
                "announcement": f"{player['name']} completes the board and wins!",
            }

        next_label = "Bull" if new_target == 25 else str(new_target)
        return {
            "player_scores": scores,
            "scored": 1,
            "message": f"Hit! Next: {next_label}",
            "announcement": f"{player['name']} hits {target}! Next up: {next_label}",
        }

    def is_game_over(self, state):
        return any(v > self._max_target() for v in state["player_scores"].values())

    def get_display_state(self, state):
        return {
            "targets": {pid: t for pid, t in self._target.items()},
            "max_target": self._max_target(),
            "include_bull": self.include_bull,
            "doubles_skip": self.doubles_skip,
            "triples_skip": self.triples_skip,
        }

    def restore_state(self, state):
        self._target = {p["id"]: state["player_scores"].get(p["id"], 1)
                        for p in state["players"]}

    def sync_scores(self, scores):
        for pid, val in scores.items():
            self._target[pid] = val


MODE_CLASS = AroundTheClockMode
