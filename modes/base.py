"""
Base class for all game modes.
Each mode plugin must subclass this and set MODE_CLASS at module level.
"""
from typing import Optional


class BaseMode:
    mode_id: str = "base"
    mode_name: str = "Base"
    description: str = ""
    options_schema: dict = {}

    def __init__(self, players: list, options: dict):
        self.players = players
        self.options = options

    def initial_scores(self) -> dict:
        """Return the starting player_scores dict {player_id: score_value}."""
        return {p["id"]: 0 for p in self.players}

    def on_dart(self, state: dict, player: dict, segment: int, ring: str, raw_score: int) -> dict:
        """
        Process a dart throw.
        Must return a dict with at minimum:
          - player_scores: updated scores dict
          - scored: points awarded this dart
        Optional keys:
          - bust: True if turn is invalid and scores reset
          - advance_turn: True to end turn early (before 3 darts)
          - winner_id: player id if this dart wins the game
          - message: short result message
          - announcement: text for TTS/display announcement
        """
        raise NotImplementedError

    def is_game_over(self, state: dict) -> bool:
        raise NotImplementedError

    def get_display_state(self, state: dict) -> dict:
        """Return mode-specific display data for the UI."""
        return {}

    def on_turn_start(self, state: dict):
        """Called when a new turn begins. Override if needed."""
        pass

    def restore_state(self, state: dict):
        """Called after undo to re-sync internal mode state."""
        pass

    def sync_scores(self, scores: dict):
        """Called after a manual score override."""
        pass
