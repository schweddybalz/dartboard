"""
Limbo – Players share a moving bar. Score under the bar and the bar drops to your score.
Score at or over the bar and you lose a life; bar resets to starting value.
Miss = 25 points. Last player with lives wins.
"""
from modes.base import BaseMode


class LimboMode(BaseMode):
    mode_id = "limbo"
    mode_name = "Limbo"
    description = "Score under the bar — it drops to your score. Hit or exceed the bar and lose a life!"
    options_schema = {
        "starting_bar": {"type": "integer", "default": 60,
                         "description": "Starting bar value. Score this or more = lose a life."},
        "lives":        {"type": "integer", "default": 3,
                         "description": "Lives each player starts with."},
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.starting_bar = options.get("starting_bar", 60)
        self.starting_lives = options.get("lives", 3)
        self.darts_per_turn = options.get("darts_per_turn", 3)
        self._lives = {p["id"]: self.starting_lives for p in players}
        self._eliminated = {p["id"]: False for p in players}
        self._turn_total = {p["id"]: 0 for p in players}
        self._current_bar = self.starting_bar
        self._turn_start_bar = self.starting_bar
        self._elimination_order = []
        self._turn_ended = {p["id"]: False for p in players}

    def initial_scores(self):
        return {p["id"]: self.starting_lives for p in self.players}

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        scores = dict(state["player_scores"])

        if self._eliminated[pid]:
            return {
                "player_scores": scores,
                "scored": 0,
                "advance_turn": True,
                "message": f"{player['name']} is eliminated — skipping",
            }

        # If turn already resolved, ignore extra darts
        if self._turn_ended.get(pid):
            return {
                "player_scores": scores,
                "scored": 0,
                "message": "Turn already done — press Next Player",
            }

        # Miss counts as 25
        dart_value = 25 if ring == "miss" else raw_score
        self._turn_total[pid] = self._turn_total.get(pid, 0) + dart_value
        running = self._turn_total[pid]

        darts_thrown = len(state.get("darts_this_turn", [])) + 1
        turn_done = darts_thrown >= self.darts_per_turn or running >= self._current_bar

        if not turn_done:
            return {
                "player_scores": scores,
                "scored": dart_value,
                "message": f"Running: {running} / bar: {self._current_bar}",
            }

        # End of turn
        turn_score = self._turn_total[pid]
        self._turn_total[pid] = 0

        self._turn_ended[pid] = True
        if turn_score >= self._turn_start_bar:
            # Lose a life, bar resets
            self._lives[pid] = max(0, self._lives[pid] - 1)
            scores[pid] = self._lives[pid]
            self._current_bar = self.starting_bar

            if self._lives[pid] == 0:
                self._eliminated[pid] = True
                self._elimination_order.append(pid)
                alive_count = sum(1 for p in self.players if not self._eliminated.get(p["id"], False))
                return {
                    "player_scores": scores,
                    "scored": dart_value,
                    "advance_turn": False,
                    "no_auto_advance": True,
                    "message": f"{player['name']} scored {turn_score} — ELIMINATED!",
                    "announcement": f"💀 {player['name']} hit the bar with {turn_score}! Out of lives — eliminated! Bar resets to {self.starting_bar}.",
                    "life_lost": {"player_id": pid, "player_name": player['name'], "lives_remaining": 0, "starting_lives": self.starting_lives, "eliminated": True, "game_over": alive_count <= 1},
                }
            return {
                "player_scores": scores,
                "scored": dart_value,
                "advance_turn": False,
                "no_auto_advance": True,
                "message": f"{player['name']} scored {turn_score} — hit the bar! {self._lives[pid]} lives left. Bar resets.",
                "announcement": f"💔 {player['name']} hit the bar with {turn_score}! Loses a life ({self._lives[pid]} left). Bar resets to {self.starting_bar}.",
                "life_lost": {"player_id": pid, "player_name": player['name'], "lives_remaining": self._lives[pid], "starting_lives": self.starting_lives, "eliminated": self._lives[pid] == 0, "game_over": False},
            }
        else:
            # Safe — bar drops to this score
            old_bar = self._turn_start_bar
            self._current_bar = turn_score
            return {
                "player_scores": scores,
                "scored": dart_value,
                "advance_turn": False,
                "no_auto_advance": True,
                "play_good": True,
                "message": f"{player['name']} scored {turn_score} — safe! Bar drops from {old_bar} to {turn_score}.",
                "announcement": f"✅ {player['name']} scores {turn_score}. Under the bar! Bar drops to {turn_score}.",
            }

    def is_game_over(self, state):
        alive = [pid for pid, elim in self._eliminated.items() if not elim]
        if len(alive) <= 1:
            if alive:
                state["winner_id"] = alive[0]
            return True
        return False

    def get_display_state(self, state):
        pid = state["players"][state["current_player_idx"]]["id"]
        darts = state.get("darts_this_turn", [])
        turn_done = self._turn_ended.get(pid, False) or len(darts) >= self.darts_per_turn
        return {
            "current_bar": self._current_bar,
            "turn_start_bar": self._turn_start_bar,
            "starting_bar": self.starting_bar,
            "lives": self._lives,
            "starting_lives": self.starting_lives,
            "eliminated": self._eliminated,
            "turn_totals": self._turn_total,
            "turn_done": turn_done,
            "elimination_order": self._elimination_order,
        }

    def is_player_eliminated(self, pid):
        return self._eliminated.get(pid, False)

    def on_turn_start(self, state):
        pid = state["players"][state["current_player_idx"]]["id"]
        self._turn_total[pid] = 0
        self._turn_ended[pid] = False
        self._turn_start_bar = self._current_bar  # snapshot bar at turn start

    def restore_state(self, state):
        self._lives = {p["id"]: self.starting_lives for p in state["players"]}
        self._eliminated = {p["id"]: False for p in state["players"]}
        self._turn_total = {p["id"]: 0 for p in state["players"]}
        self._turn_ended = {p["id"]: False for p in state["players"]}
        self._elimination_order = []
        self._current_bar = self.starting_bar


MODE_CLASS = LimboMode
