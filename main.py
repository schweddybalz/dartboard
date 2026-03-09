"""
Smart Dartboard – Game Engine
FastAPI server: REST API + WebSocket broadcast
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI, HTTPException, WebSocket, WebSocketDisconnect,
    UploadFile, File, Form
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from engine import GameEngine
from models import (
    NewGameRequest, DartRequest, OverrideRequest,
    NewPlayerRequest, AnnouncementEvent
)
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

db = Database("data/dartboard.db")
engine = GameEngine(db)

# ── WebSocket connection manager ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WS connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        logger.info(f"WS disconnected. Total: {len(self.active)}")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

manager = ConnectionManager()

# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    logger.info("Database initialised")
    yield
    logger.info("Shutdown")

app = FastAPI(title="Smart Dartboard Engine", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded avatars
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def serve_companion():
    return FileResponse("dartboard_companion.html")

@app.get("/tv")
def serve_tv():
    return FileResponse("dartboard_tv.html")


# ── Helper ────────────────────────────────────────────────────────────────────

async def push(event_type: str, payload: dict):
    """Broadcast a typed event to all WebSocket clients."""
    await manager.broadcast({"event": event_type, "payload": payload, "ts": datetime.utcnow().isoformat()})


# ── Player endpoints ──────────────────────────────────────────────────────────

@app.get("/players")
def list_players():
    return db.get_all_players()

@app.post("/players")
def create_player(req: NewPlayerRequest):
    player = db.create_player(req.name, req.avatar_url)
    return player

@app.post("/players/{player_id}/avatar")
async def upload_avatar(player_id: str, file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        raise HTTPException(400, "Unsupported image type")
    filename = f"{player_id}{ext}"
    dest = UPLOAD_DIR / filename
    content = await file.read()
    dest.write_bytes(content)
    url = f"/uploads/{filename}"
    db.update_player_avatar(player_id, url)
    return {"avatar_url": url}

@app.get("/players/{player_id}/stats")
def player_stats(player_id: str):
    stats = db.get_player_stats(player_id)
    if not stats:
        raise HTTPException(404, "Player not found")
    return stats

@app.delete("/players/{player_id}")
def delete_player(player_id: str):
    deleted = db.delete_player(player_id)
    if not deleted:
        raise HTTPException(404, "Player not found")
    return {"deleted": player_id}


# ── Game endpoints ────────────────────────────────────────────────────────────

@app.get("/modes")
def list_modes():
    return engine.list_modes()

@app.post("/game/new")
async def new_game(req: NewGameRequest):
    try:
        state = engine.new_game(req)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await push("game_started", state)
    return state

@app.get("/game/state")
def get_state():
    state = engine.get_state()
    if not state:
        raise HTTPException(404, "No active game")
    return state

@app.post("/game/dart")
async def throw_dart(req: DartRequest):
    """Submit a dart hit (from camera pipeline or manual input)."""
    try:
        result = engine.process_dart(req.segment, req.ring, req.player_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await push("dart_scored", result)
    if result.get("game_over"):
        await push("game_over", result)
    # Fire announcement hook
    if result.get("announcement"):
        await push("announcement", {"text": result["announcement"], "player_id": result.get("current_player_id")})
    return result

@app.post("/game/override")
async def override_score(req: OverrideRequest):
    """Manually correct a player's score."""
    try:
        state = engine.override_score(req.player_id, req.new_score, req.reason)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await push("score_overridden", {"player_id": req.player_id, "new_score": req.new_score, "reason": req.reason, "state": state})
    return state

@app.post("/game/undo")
async def undo_dart():
    """Undo the last dart throw."""
    try:
        state = engine.undo()
    except ValueError as e:
        raise HTTPException(400, str(e))
    await push("dart_undone", state)
    return state

@app.post("/game/next-turn")
async def next_turn():
    """Manually advance to next player's turn."""
    try:
        state = engine.next_turn()
    except ValueError as e:
        raise HTTPException(400, str(e))
    await push("turn_changed", state)
    return state

@app.post("/game/end")
async def end_game():
    """Forfeit / end the current game early."""
    state = engine.end_game()
    await push("game_ended", state)
    return state

@app.post("/game/announce")
async def announce(ev: AnnouncementEvent):
    """Push a custom announcement to all clients (e.g., from TTS system)."""
    await push("announcement", {"text": ev.text, "player_id": ev.player_id})
    return {"ok": True}


# ── History endpoints ─────────────────────────────────────────────────────────

@app.get("/history")
def game_history(limit: int = 20, player_id: Optional[str] = None):
    return db.get_game_history(limit=limit, player_id=player_id)

@app.get("/history/{game_id}")
def game_detail(game_id: str):
    game = db.get_game_detail(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    return game


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # Send current state immediately on connect
    state = engine.get_state()
    if state:
        await ws.send_json({"event": "state_sync", "payload": state, "ts": datetime.utcnow().isoformat()})
    try:
        while True:
            # Keep connection alive; client can send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Camera stub endpoint ──────────────────────────────────────────────────────

@app.post("/camera/dart")
async def camera_dart(req: DartRequest):
    """
    Stub endpoint for the camera pipeline.
    The CV system will POST here when it detects a dart.
    Identical to /game/dart but labelled separately for clarity.
    """
    return await throw_dart(req)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
