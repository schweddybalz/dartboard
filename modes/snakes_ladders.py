"""
Snakes & Ladders – Dart-powered board game.
Each dart moves a player by its die value. 3 darts per turn, each dart moves independently.
Landing on a ladder base climbs up; landing on a snake head slides down.
6 rounds max; first to square 65+ wins. If nobody wins, standings by position.

Die values:
  double        → 1
  outer_single  → 2
  triple        → 3
  inner_single  → 4
  bull          → 5
  bullseye      → 6
  miss          → 0
"""
from modes.base import BaseMode


LADDERS = {
    3:  18,
    7:  14,
    13: 58,   # Stairway to Heaven
    25: 46,
    35: 56,
    45: 64,
}

SNAKES = {
    16: 5,
    30: 9,
    42: 1,    # Monty Python
    52: 33,   # Jake the Snake
    60: 49,
    62: 1,    # Tunnel Snake
}

SNAKE_NAMES = {
    42: "Monty Python",
    52: "Jake the Snake",
    62: "Tunnel Snake",
}

LADDER_NAMES = {
    13: "Stairway to Heaven",
}

FINISH = 65
BOARD_SIZE = 64
TOTAL_ROUNDS = 6

RING_DIE = {
    "double":       1,
    "outer_single": 2,
    "triple":       3,
    "inner_single": 4,
    "bull":         5,
    "bullseye":     6,
    "miss":         0,
    "single":       2,
}


class SnakesLaddersMode(BaseMode):
    mode_id = "snakes_ladders"
    mode_name = "Tunnel Snakes & Ladders"
    description = "Dart-powered Snakes & Ladders! Each dart moves you. Hit a ladder — climb up. Hit a snake — slide down. 6 rounds, furthest wins!"
    options_schema = {
        "total_rounds": {
            "type": "integer",
            "default": 6,
            "description": "Number of rounds to play (default 6).",
        },
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self._total_rounds = options.get("total_rounds", TOTAL_ROUNDS)
        self._positions = {p["id"]: 0 for p in players}
        self._finished = {}
        self._finish_order = []
        self._events = []
        self._round_number = 0

    def initial_scores(self):
        return {p["id"]: 0 for p in self.players}

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        scores = dict(state["player_scores"])
        self._events = []

        die = RING_DIE.get(ring, 0)
        old_pos = self._positions[pid]
        new_pos = old_pos + die

        event = {
            "pid": pid,
            "die": die,
            "ring": ring,
            "from": old_pos,
            "to": new_pos,
            "slide_from": None,
            "slide_to": None,
            "slide_type": None,
            "slide_name": None,
            "finished": False,
        }

        announcement = None
        advance_turn = False

        if die == 0:
            announcement = f"{player['name']} misses — no move!"
        elif new_pos >= FINISH:
            new_pos = FINISH
            self._positions[pid] = new_pos
            scores[pid] = new_pos
            event["to"] = new_pos
            event["finished"] = True
            advance_turn = True
            if pid not in self._finished:
                self._finished[pid] = self._round_number
                self._finish_order.append(pid)
                place = len(self._finish_order)
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(place, "th")
                announcement = f"🏆 {player['name']} finishes in {place}{suffix} place!"
        else:
            self._positions[pid] = new_pos
            scores[pid] = new_pos

            if new_pos in LADDERS:
                slide_to = LADDERS[new_pos]
                name = LADDER_NAMES.get(new_pos, "a ladder")
                event["slide_from"] = new_pos
                event["slide_to"] = slide_to
                event["slide_type"] = "ladder"
                event["slide_name"] = name
                self._positions[pid] = slide_to
                scores[pid] = slide_to
                event["to"] = slide_to
                announcement = f"🪜 {player['name']} hits {name}! Climbs from {new_pos} to {slide_to}!"

            elif new_pos in SNAKES:
                slide_to = SNAKES[new_pos]
                name = SNAKE_NAMES.get(new_pos, "a snake")
                event["slide_from"] = new_pos
                event["slide_to"] = slide_to
                event["slide_type"] = "snake"
                event["slide_name"] = name
                self._positions[pid] = slide_to
                scores[pid] = slide_to
                event["to"] = slide_to
                announcement = f"🐍 {player['name']} hits {name}! Slides from {new_pos} to {slide_to}!"

        self._events = [event]

        # Advance turn on 3rd dart or when player finishes
        dart_num = len(state.get("darts_this_turn", [])) + 1
        should_advance = advance_turn or dart_num >= 3

        return {
            "player_scores": scores,
            "scored": die,
            "advance_turn": should_advance,
            "message": announcement or f"{player['name']} rolls {die}, moves {old_pos}→{self._positions[pid]}",
            "announcement": announcement,
        }

    def is_player_eliminated(self, pid: str) -> bool:
        return pid in self._finished

    def is_game_over(self, state):
        all_pids = [p["id"] for p in self.players]

        # All players finished
        if all(pid in self._finished for pid in all_pids):
            self._set_winner(state)
            return True

        # Only one unfinished player left (and there are multiple players)
        unfinished = [pid for pid in all_pids if pid not in self._finished]
        if len(unfinished) == 1 and len(self.players) > 1:
            last_pid = unfinished[0]
            if last_pid not in self._finished:
                self._finished[last_pid] = self._round_number
                self._finish_order.append(last_pid)
            self._set_winner(state)
            return True

        # Max rounds completed
        if self._round_number > self._total_rounds:
            self._set_winner(state)
            return True

        return False

    def _set_winner(self, state):
        if self._finish_order:
            state["winner_id"] = self._finish_order[0]
        else:
            best = max(self._positions.items(), key=lambda x: x[1])
            state["winner_id"] = best[0]

    def get_display_state(self, state):
        finished_pids = list(self._finish_order)
        unfinished = sorted(
            [pid for pid in self._positions if pid not in self._finished],
            key=lambda pid: self._positions[pid],
            reverse=True,
        )
        standings = finished_pids + unfinished

        return {
            "positions": dict(self._positions),
            "finished": dict(self._finished),
            "finish_order": list(self._finish_order),
            "standings": standings,
            "events": list(self._events),
            "round_number": self._round_number,
            "total_rounds": self._total_rounds,
            "ladders": LADDERS,
            "snakes": SNAKES,
            "snake_names": SNAKE_NAMES,
            "ladder_names": LADDER_NAMES,
            "finish": FINISH,
            "board_size": BOARD_SIZE,
        }

    def on_turn_start(self, state):
        # Increment round when we cycle back to the first active player
        active_players = [p for p in self.players if p["id"] not in self._finished]
        if active_players:
            first_active_id = active_players[0]["id"]
            current_pid = self.players[state["current_player_idx"]]["id"]
            if current_pid == first_active_id:
                self._round_number += 1

    def restore_state(self, state):
        scores = state["player_scores"]
        for pid in self._positions:
            self._positions[pid] = scores.get(pid, 0)
        self._finished = {
            pid: 0 for pid in self._positions if self._positions[pid] >= FINISH
        }
        self._finish_order = [pid for pid in self._finish_order if pid in self._finished]
        self._events = []


MODE_CLASS = SnakesLaddersMode
