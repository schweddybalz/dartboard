"""
Kick Down – Race from 0 to exactly 301/501.
Score points upward each turn. Hit an opponent's exact score → they reset to 0 (KICK DOWN!).
Go over the target → your score is set to (target - penalty).
Penalty on bust: Random (1-180), 100, or 150.
"""
import random
from modes.base import BaseMode


class KickDownMode(BaseMode):
    mode_id = "kick_down"
    mode_name = "Kick Down"
    description = "Race from 0 to 301/501. Match an opponent's score to kick them back to 0! Bust and lose points."
    options_schema = {
        "target": {
            "type": "integer",
            "default": 301,
            "options": [301, 501],
            "description": "Score to reach exactly to win.",
        },
        "over_penalty": {
            "type": "string",
            "default": "random",
            "options": ["random", "100", "150"],
            "description": "Points deducted from target on bust: random (1-180), 100, or 150.",
        },
        "double_in": {
            "type": "boolean",
            "default": False,
            "description": "Require a double to start scoring.",
        },
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.target = options.get("target", 301)
        self.over_penalty_opt = options.get("over_penalty", "random")
        self.double_in = options.get("double_in", False)
        self._opened = {p["id"]: not self.double_in for p in players}
        self._turn_start_scores = {}  # scores at start of each turn for bust revert

    def _penalty(self):
        if self.over_penalty_opt == "100":
            return 100
        if self.over_penalty_opt == "150":
            return 150
        return random.randint(1, 180)

    def initial_scores(self):
        return {p["id"]: 0 for p in self.players}

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        scores = dict(state["player_scores"])
        dart_num = len(state.get("darts_this_turn", [])) + 1

        # Snapshot scores at start of turn (first dart only)
        if dart_num == 1:
            self._turn_start_scores = dict(scores)

        # Double-in check
        if not self._opened[pid]:
            if ring in ("double", "bullseye"):
                self._opened[pid] = True
            else:
                return {
                    "player_scores": scores,
                    "scored": 0,
                    "message": "Need a double to open!",
                    "announcement": f"{player['name']} needs a double to start!",
                }

        current = scores[pid]
        new_score = current + raw_score

        # Bust — went over target
        if new_score > self.target:
            penalty = self._penalty()
            busted_to = max(0, self.target - penalty)
            # Revert all other darts this turn too — reset to turn start score then apply bust
            scores[pid] = busted_to
            return {
                "player_scores": scores,
                "scored": 0,
                "bust": True,
                "advance_turn": True,
                "message": f"Bust! -{penalty} → {busted_to}",
                "announcement": f"💥 BUST! {player['name']} drops to {busted_to}!",
            }

        # Exact target — winner
        if new_score == self.target:
            scores[pid] = new_score
            return {
                "player_scores": scores,
                "scored": raw_score,
                "winner_id": pid,
                "advance_turn": True,
                "message": f"{player['name']} wins!",
                "announcement": f"🏆 {player['name']} hits {self.target} exactly — WINS!",
            }

        # Normal score
        scores[pid] = new_score

        # Check for Kick Down — did we land on any opponent's exact score?
        kicked = []
        for p in self.players:
            opid = p["id"]
            if opid == pid:
                continue
            if scores[opid] == new_score and scores[opid] > 0:
                scores[opid] = 0
                kicked.append(p["name"])

        kick_msg = ""
        kick_ann = None
        if kicked:
            names = " & ".join(kicked)
            kick_msg = f" 💥 KICK DOWN {names}!"
            kick_ann = f"💥 KICK DOWN! {player['name']} sends {names} back to zero!"

        return {
            "player_scores": scores,
            "scored": raw_score,
            "message": f"{new_score}{kick_msg}",
            "announcement": kick_ann,
            "kicked_players": kicked,
        }

    def is_game_over(self, state):
        return any(v >= self.target for v in state["player_scores"].values())

    def get_display_state(self, state):
        scores = state["player_scores"]
        return {
            "target": self.target,
            "double_in": self.double_in,
            "over_penalty_opt": self.over_penalty_opt,
            "scores": dict(scores),
            "remaining": {pid: self.target - scores[pid] for pid in scores},
        }

    def restore_state(self, state):
        self._opened = {p["id"]: not self.double_in for p in self.players}
        self._turn_start_scores = dict(state.get("player_scores", {}))


MODE_CLASS = KickDownMode
