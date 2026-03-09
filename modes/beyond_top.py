"""
Beyond Top – Gran Darts rules.
10 rounds. Each player must beat the previous player's score each round.
Fail = lose 1 life (start with 6). Round starts with a target of 30.
Earn 1 point per 10 points scored above the previous score.
Most points wins (or last standing if eliminations occur).
"""
from modes.base import BaseMode

TOTAL_ROUNDS = 10
STARTING_LIVES = 6
INITIAL_TARGET = 30


class BeyondTopMode(BaseMode):
    mode_id = "beyond_top"
    mode_name = "Beyond Top"
    description = "Beat the previous player's score each round or lose a life. 10 rounds, 6 lives."
    options_schema = {
        "rounds": {"type": "integer", "default": 10, "min": 3, "max": 20,
                   "description": "Number of rounds to play"},
        "lives": {"type": "integer", "default": 6, "min": 1, "max": 9,
                  "description": "Starting lives per player"},
        "starting_target": {"type": "integer", "default": 30, "min": 0, "max": 60,
                            "description": "Score the first player must beat in round 1"},
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.total_rounds = options.get("rounds", TOTAL_ROUNDS)
        self.starting_lives = options.get("lives", STARTING_LIVES)
        self.starting_target = options.get("starting_target", INITIAL_TARGET)

        self._lives = {p["id"]: self.starting_lives for p in players}
        self._points = {p["id"]: 0 for p in players}       # bonus points earned
        self._eliminated = {p["id"]: False for p in players}
        self._current_round = 1
        self._turn_score = 0        # running total for current player's turn
        self._target = self.starting_target  # score to beat this turn
        self._prev_score = self.starting_target  # last player's score (or initial target)
        self._round_target_reset = self.starting_target  # target at start of each round

    def initial_scores(self):
        # player_scores stores lives (used for life pip display)
        return {p["id"]: self.starting_lives for p in self.players}

    def is_player_eliminated(self, pid):
        return self._eliminated.get(pid, False)

    def on_turn_start(self, state):
        """Called at the start of each turn. Reset turn score and detect new round."""
        self._turn_score = 0
        pid = state["players"][state["current_player_idx"]]["id"]

        # Detect new round: this player is the first alive player in the rotation
        # Find the first non-eliminated player in player order
        first_alive_idx = None
        for i, p in enumerate(state["players"]):
            if not self._eliminated.get(p["id"], False):
                first_alive_idx = i
                break

        if state["current_player_idx"] == first_alive_idx:
            # Recalculate round number based on how many full rotations of alive players
            # have completed — use turn_number as a proxy
            alive_count = sum(1 for p in state["players"] if not self._eliminated.get(p["id"], False))
            if alive_count > 0:
                self._current_round = (state["turn_number"] - 1) // len(state["players"]) + 1
            # Reset target for the new round
            self._target = self._round_target_reset
            self._prev_score = self._round_target_reset

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        scores = dict(state["player_scores"])

        if self._eliminated[pid]:
            return {"player_scores": scores, "scored": 0, "message": f"{player['name']} is eliminated"}

        self._turn_score += raw_score

        dart_num = len(state.get("darts_this_turn", [])) + 1

        # Only evaluate after 3 darts (turn end handled naturally by engine)
        # We return the running total as scored so the last dart completes the turn
        if dart_num < 3:
            return {
                "player_scores": scores,
                "scored": raw_score,
                "message": f"Running total: {self._turn_score} (need > {self._target})",
            }

        # 3rd dart — evaluate the full turn
        total = self._turn_score
        target = self._target

        if total > target:
            # Success — earn bonus points
            bonus = (total - target) // 10
            self._points[pid] += bonus
            self._prev_score = total
            self._target = total  # next player must beat this
            msg = f"{player['name']} scored {total}! Beat {target}."
            if bonus:
                msg += f" +{bonus} bonus point{'s' if bonus != 1 else ''}!"
            ann = msg
        else:
            # Failed to beat — lose a life
            self._lives[pid] = max(0, self._lives[pid] - 1)
            scores[pid] = self._lives[pid]
            if self._lives[pid] == 0:
                self._eliminated[pid] = True
            # Target resets: next player must beat the same target as this player had
            # (failed player doesn't raise the bar)
            self._prev_score = target   # bar stays at what this player had to beat
            self._target = target
            msg = f"{player['name']} scored {total}, needed > {target}. Lost a life! ({self._lives[pid]} left)"
            ann = msg

        return {
            "player_scores": scores,
            "scored": raw_score,
            "message": msg,
            "announcement": ann,
        }

    def is_game_over(self, state):
        alive = [pid for pid, elim in self._eliminated.items() if not elim]
        # Single player left = winner
        if len(alive) == 1:
            state["winner_id"] = alive[0]
            return True
        # All rounds complete — use _current_round which is maintained by on_turn_start
        if self._current_round > self.total_rounds:
            # Winner = highest points among alive players
            best = max(alive, key=lambda pid: self._points[pid])
            state["winner_id"] = best
            return True
        return False

    def get_display_state(self, state):
        return {
            "lives": self._lives,
            "points": self._points,
            "eliminated": self._eliminated,
            "current_round": self._current_round,
            "total_rounds": self.total_rounds,
            "starting_lives": self.starting_lives,
            "current_target": self._target,
            "turn_score": self._turn_score,
        }

    def restore_state(self, state):
        scores = state.get("player_scores", {})
        self._lives = dict(scores)
        self._eliminated = {pid: (lives == 0) for pid, lives in self._lives.items()}
        self._turn_score = 0
        # Recompute round from turn number
        n = len(state.get("players", self.players))
        turn = state.get("turn_number", 1)
        self._current_round = (turn - 1) // n + 1


MODE_CLASS = BeyondTopMode
