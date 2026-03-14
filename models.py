"""
Pydantic models for all request bodies.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class NewPlayerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    avatar_url: Optional[str] = None


class NewGameRequest(BaseModel):
    mode: str                          # e.g. "501", "cricket", "around_the_clock"
    player_ids: List[str]              # ordered list of player UUIDs
    options: dict = {}                 # mode-specific options, e.g. {"start_score": 301}


class DartRequest(BaseModel):
    segment: int = Field(..., ge=0, le=25)   # 0 = miss, 1–20 = number, 25 = bull
    ring: str = Field(...)                    # "single", "double", "triple", "bull", "bullseye", "miss"
    player_id: Optional[str] = None          # if None, uses current player


class OverrideRequest(BaseModel):
    player_id: str
    new_score: int
    reason: str = "Manual override"


class PlayerColorRequest(BaseModel):
    color: Optional[str] = None  # hex string e.g. "#e63946", or null to clear


class AnnouncementEvent(BaseModel):
    text: str
    player_id: Optional[str] = None
