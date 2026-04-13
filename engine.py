"""
Game Engine – orchestrates active game state, delegates to mode plugins.
"""
import importlib
import pkgutil
from pathlib import Path
from typing import Optional

from database import Database
from models import NewGameRequest


RING_MULTIPLIERS = {
    "miss":     0,
    "single":   1,
    "double":   2,
    "triple":   3,
    "bull":     1,   # outer bull = 25
    "bullseye": 2,   # inner bull = 50
}

RING_SCORES = {
    "miss":     0,
    "bull":     25,
    "bullseye": 50,
}


def calc_score(segment: int, ring: str) -> int:
    """Convert a raw segment + ring into a point value."""
    if ring in ("bull", "bullseye"):
        return RING_SCORES[ring]
    if ring == "miss":
        return 0
    return segment * RING_MULTIPLIERS.get(ring, 1)


class GameEngine:
    def __init__(self, db: Database):
        self.db = db
        self._modes = {}
        self._load_modes()
        self._state: Optional[dict] = None
        self._mode_instance = None
        self._history: list[dict] = []   # undo stack

    # ── Mode loading ─────────────────────────────────────────────────────────

    def _load_modes(self):
        modes_path = Path(__file__).parent / "modes"
        for finder, name, _ in pkgutil.iter_modules([str(modes_path)]):
            mod = importlib.import_module(f"modes.{name}")
            if hasattr(mod, "MODE_CLASS"):
                cls = mod.MODE_CLASS
                self._modes[cls.mode_id] = cls

    def list_modes(self) -> list:
        return [
            {"id": cls.mode_id, "name": cls.mode_name, "description": cls.description,
             "options_schema": cls.options_schema}
            for cls in self._modes.values()
        ]

    # ── Game lifecycle ───────────────────────────────────────────────────────

    def new_game(self, req: NewGameRequest) -> dict:
        if req.mode not in self._modes:
            raise ValueError(f"Unknown game mode: {req.mode}")
        if len(req.player_ids) < 1:
            raise ValueError("At least one player required")

        # Validate players exist
        players = []
        for pid in req.player_ids:
            p = self.db.get_player(pid)
            if not p:
                raise ValueError(f"Player not found: {pid}")
            players.append(p)

        game_id = self.db.create_game(req.mode, req.options, req.player_ids)
        mode_cls = self._modes[req.mode]
        self._mode_instance = mode_cls(players, req.options)
        # Allow mode to specify a custom turn order (e.g. cricket interleaved teams)
        if hasattr(self._mode_instance, "player_order"):
            ordered_ids = self._mode_instance.player_order
            players = sorted(players, key=lambda p: ordered_ids.index(p["id"])
                             if p["id"] in ordered_ids else 999)
        self._state = {
            "game_id": game_id,
            "mode": req.mode,
            "mode_name": mode_cls.mode_name,
            "options": req.options,
            "players": players,
            "player_scores": self._mode_instance.initial_scores(),
            "current_player_idx": 0,
            "turn_number": 1,
            "darts_this_turn": [],
            "game_over": False,
            "winner_id": None,
            "turn_history": [],
        }
        self._history = []
        # Apply initial turn start so team games start on the right player
        if hasattr(self._mode_instance, "on_turn_start"):
            self._mode_instance.on_turn_start(self._state)
        return self._public_state()

    def get_state(self) -> Optional[dict]:
        if not self._state or self._state.get("game_over"):
            return None
        return self._public_state()

    def end_game(self) -> dict:
        if not self._state:
            raise ValueError("No active game")
        self._state["game_over"] = True
        self.db.end_game(self._state["game_id"], self._state["winner_id"], self._public_state())
        return self._public_state()

    # ── Dart processing ──────────────────────────────────────────────────────

    def process_dart(self, segment: int, ring: str, player_id: Optional[str] = None) -> dict:
        if not self._state or self._state["game_over"]:
            raise ValueError("No active game")

        # Push undo snapshot
        import copy
        self._history.append(copy.deepcopy(self._state))

        state = self._state
        players = state["players"]
        cur_idx = state["current_player_idx"]
        current_player = players[cur_idx]

        if player_id and player_id != current_player["id"]:
            raise ValueError(f"It is {current_player['name']}'s turn")

        raw_score = calc_score(segment, ring)
        dart_num = len(state["darts_this_turn"]) + 1

        # Delegate to mode
        result = self._mode_instance.on_dart(
            state, current_player, segment, ring, raw_score
        )

        dart_record = {
            "player_id": current_player["id"],
            "player_name": current_player["name"],
            "segment": segment,
            "ring": ring,
            "raw_score": raw_score,
            "scored": result.get("scored", raw_score),
            "bust": result.get("bust", False),
            "turn_number": state["turn_number"],
            "dart_number": dart_num,
            "message": result.get("message", ""),
        }
        state["darts_this_turn"].append(dart_record)

        # Persist dart to DB
        self.db.record_dart(
            state["game_id"], current_player["id"],
            state["turn_number"], dart_num,
            segment, ring, result.get("scored", raw_score)
        )

        # Apply score update from mode (mode is responsible for reverting on bust)
        state["player_scores"] = result.get("player_scores", state["player_scores"])

        # Check win condition
        if self._mode_instance.is_game_over(state):
            state["game_over"] = True
            state["winner_id"] = result.get("winner_id", current_player["id"])
            self.db.end_game(state["game_id"], state["winner_id"], self._public_state())

        # Only advance when mode explicitly requests it (e.g. S&L finish, killer assignment)
        # Normal turn end is driven by companion's Next Player button → /game/next-turn
        advance = result.get("advance_turn", False)
        if advance:
            if not state["game_over"]:
                self._advance_turn()

        announcement = self._build_announcement(result, dart_record, state)

        return {
            **self._public_state(),
            "dart": dart_record,
            "announcement": announcement,
        }

    def _advance_turn(self):
        state = self._state
        n = len(state["players"])
        # Archive this turn
        state["turn_history"].append({
            "player_id": state["players"][state["current_player_idx"]]["id"],
            "turn_number": state["turn_number"],
            "darts": list(state["darts_this_turn"]),
        })
        state["darts_this_turn"] = []
        state["turn_number"] += 1
        state["current_player_idx"] = (state["current_player_idx"] + 1) % n
        # Skip eliminated players (advance turn_number for each skip so round
        # counting stays correct, but don't archive a fake turn for them)
        if hasattr(self._mode_instance, "is_player_eliminated"):
            for _ in range(n):  # guard against infinite loop if all eliminated
                pid = state["players"][state["current_player_idx"]]["id"]
                if not self._mode_instance.is_player_eliminated(pid):
                    break
                state["turn_number"] += 1
                state["current_player_idx"] = (state["current_player_idx"] + 1) % n
        # Advance team turn tracking before on_turn_start corrects the player
        if hasattr(self._mode_instance, "advance_team_turn"):
            self._mode_instance.advance_team_turn()
        # Notify mode of turn change (may redirect current_player_idx for teams)
        if hasattr(self._mode_instance, "on_turn_start"):
            self._mode_instance.on_turn_start(state)

    def next_turn(self) -> dict:
        if not self._state or self._state["game_over"]:
            raise ValueError("No active game")
        self._advance_turn()
        return self._public_state()

    def undo(self) -> dict:
        if not self._history:
            raise ValueError("Nothing to undo")
        self._state = self._history.pop()
        # Re-sync mode instance scores from restored state
        if hasattr(self._mode_instance, "restore_state"):
            self._mode_instance.restore_state(self._state)
        return self._public_state()

    def override_score(self, player_id: str, new_score: int, reason: str) -> dict:
        if not self._state:
            raise ValueError("No active game")
        scores = self._state["player_scores"]
        if player_id not in scores:
            raise ValueError(f"Player {player_id} not in current game")
        old_score = scores[player_id]
        self.db.record_override(self._state["game_id"], player_id, old_score, new_score, reason)
        scores[player_id] = new_score
        self._state["player_scores"] = scores
        # Sync to mode instance
        if hasattr(self._mode_instance, "sync_scores"):
            self._mode_instance.sync_scores(scores)
        return self._public_state()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _public_state(self) -> dict:
        s = self._state
        mode_display = {}
        if self._mode_instance:
            mode_display = self._mode_instance.get_display_state(s)
        return {
            "game_id": s["game_id"],
            "mode": s["mode"],
            "mode_name": s["mode_name"],
            "options": s.get("options", {}),
            "game_over": s["game_over"],
            "winner_id": s["winner_id"],
            "current_player_id": s["players"][s["current_player_idx"]]["id"],
            "current_player_name": s["players"][s["current_player_idx"]]["name"],
            "turn_number": s["turn_number"],
            "darts_this_turn": s["darts_this_turn"],
            "player_scores": s["player_scores"],
            "players": s["players"],
            "upcoming_players": self._upcoming_players(s),
            "turn_order_history": [t["player_id"] for t in s.get("turn_history", [])][-20:],
            "mode_display": mode_display,
            "last_turn_darts": self._last_turn_darts(s),
        }

    def _upcoming_players(self, s: dict) -> list:
        """Return next 4 player IDs after the current one, in turn order.
        Asks the mode instance if it can provide the sequence (team-aware),
        otherwise falls back to walking the players array."""
        if self._mode_instance and hasattr(self._mode_instance, "upcoming_players"):
            try:
                result = self._mode_instance.upcoming_players(s)
                if result:
                    return result[:4]
            except Exception:
                pass

        players = s["players"]
        n = len(players)
        if n <= 1:
            return []
        cur_idx = s["current_player_idx"]
        upcoming = []
        for i in range(1, n + 1):
            idx = (cur_idx + i) % n
            pid = players[idx]["id"]
            if pid not in upcoming:
                upcoming.append(pid)
            if len(upcoming) >= 4:
                break
        return upcoming

    def _last_turn_darts(self, s: dict) -> dict:
        """Return {player_id: [darts]} for the most recent completed turn per player."""
        seen = {}
        for turn in reversed(s.get("turn_history", [])):
            pid = turn["player_id"]
            if pid not in seen:
                seen[pid] = turn["darts"]
        return seen

    def _build_announcement(self, result: dict, dart: dict, state: dict) -> str:
        if result.get("announcement"):
            return result["announcement"]
        score = dart["scored"]
        name = dart["player_name"]
        ring = dart["ring"]
        seg = dart["segment"]

        if dart["bust"]:
            return f"Bust! {name} goes back."
        if ring == "bullseye":
            return f"Bullseye! 50 points!"
        if ring == "bull":
            return f"Bull! 25 points!"
        if ring == "miss":
            return "Miss!"
        if ring == "triple":
            return f"Triple {seg}! {score} points!"
        if ring == "double":
            return f"Double {seg}! {score} points!"
        return f"{name} scores {score}!"
