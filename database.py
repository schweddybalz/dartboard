"""
Database layer – SQLite via Python's built-in sqlite3.
No ORM dependency; keeps things simple and portable.
"""
import sqlite3
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ── Schema ──────────────────────────────────────────────────────────────

    def init(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS players (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    avatar_url  TEXT,
                    created_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS games (
                    id          TEXT PRIMARY KEY,
                    mode        TEXT NOT NULL,
                    options     TEXT NOT NULL,   -- JSON
                    player_ids  TEXT NOT NULL,   -- JSON array
                    winner_id   TEXT,
                    started_at  TEXT NOT NULL,
                    ended_at    TEXT,
                    state       TEXT             -- JSON final state snapshot
                );

                CREATE TABLE IF NOT EXISTS darts (
                    id          TEXT PRIMARY KEY,
                    game_id     TEXT NOT NULL,
                    player_id   TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    dart_number INTEGER NOT NULL,  -- 1, 2, or 3 within the turn
                    segment     INTEGER NOT NULL,
                    ring        TEXT NOT NULL,
                    score       INTEGER NOT NULL,
                    thrown_at   TEXT NOT NULL,
                    FOREIGN KEY (game_id) REFERENCES games(id)
                );

                CREATE TABLE IF NOT EXISTS overrides (
                    id          TEXT PRIMARY KEY,
                    game_id     TEXT NOT NULL,
                    player_id   TEXT NOT NULL,
                    old_score   INTEGER,
                    new_score   INTEGER,
                    reason      TEXT,
                    created_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS live_state (
                    id          INTEGER PRIMARY KEY CHECK (id = 1),
                    state_json  TEXT NOT NULL,
                    saved_at    TEXT NOT NULL
                );
            """)
            # Migration: add color column if it doesn't exist yet
            try:
                conn.execute("ALTER TABLE players ADD COLUMN color TEXT")
            except Exception:
                pass  # Column already exists

    # ── Players ─────────────────────────────────────────────────────────────

    _PALETTE = [
        '#2862A5','#5C2D91','#00b4a0','#e63946','#f5a623',
        '#2dc653','#e87b1e','#c975d4','#00b8d9','#ff6b9d',
        '#7cb518','#ff9a3c',
    ]

    def create_player(self, name: str, avatar_url: Optional[str] = None) -> dict:
        import random
        # Pick a color not already used
        with self._conn() as conn:
            used = {r[0] for r in conn.execute("SELECT color FROM players WHERE color IS NOT NULL").fetchall()}
        available = [c for c in self._PALETTE if c not in used]
        color = random.choice(available if available else self._PALETTE)
        player = {
            "id": str(uuid.uuid4()),
            "name": name,
            "avatar_url": avatar_url,
            "color": color,
            "created_at": datetime.utcnow().isoformat(),
        }
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO players (id, name, avatar_url, color, created_at) VALUES (:id, :name, :avatar_url, :color, :created_at)",
                player
            )
        return player

    def get_player(self, player_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
            return dict(row) if row else None

    def get_all_players(self) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM players ORDER BY name").fetchall()
            return [dict(r) for r in rows]

    def update_player_avatar(self, player_id: str, avatar_url: str):
        with self._conn() as conn:
            conn.execute("UPDATE players SET avatar_url=? WHERE id=?", (avatar_url, player_id))

    def update_player_color(self, player_id: str, color: Optional[str]):
        with self._conn() as conn:
            conn.execute("UPDATE players SET color=? WHERE id=?", (color, player_id))

    def delete_player(self, player_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM players WHERE id=?", (player_id,))
            return cur.rowcount > 0

    def get_player_stats(self, player_id: str) -> Optional[dict]:
        player = self.get_player(player_id)
        if not player:
            return None
        with self._conn() as conn:
            games_played = conn.execute(
                "SELECT COUNT(*) FROM games WHERE player_ids LIKE ? AND ended_at IS NOT NULL",
                (f'%{player_id}%',)
            ).fetchone()[0]
            games_won = conn.execute(
                "SELECT COUNT(*) FROM games WHERE winner_id=?", (player_id,)
            ).fetchone()[0]
            total_darts = conn.execute(
                "SELECT COUNT(*) FROM darts WHERE player_id=?", (player_id,)
            ).fetchone()[0]
            total_score = conn.execute(
                "SELECT COALESCE(SUM(score),0) FROM darts WHERE player_id=?", (player_id,)
            ).fetchone()[0]
            highest_turn = conn.execute("""
                SELECT COALESCE(MAX(turn_score),0) FROM (
                    SELECT SUM(score) as turn_score
                    FROM darts WHERE player_id=?
                    GROUP BY game_id, turn_number
                )
            """, (player_id,)).fetchone()[0]
        return {
            **player,
            "games_played": games_played,
            "games_won": games_won,
            "total_darts": total_darts,
            "total_score": total_score,
            "average_per_dart": round(total_score / total_darts, 2) if total_darts else 0,
            "highest_turn": highest_turn,
        }

    # ── Games ────────────────────────────────────────────────────────────────

    def create_game(self, mode: str, options: dict, player_ids: list) -> str:
        game_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO games VALUES (?,?,?,?,?,?,?,?)",
                (game_id, mode, json.dumps(options), json.dumps(player_ids),
                 None, datetime.utcnow().isoformat(), None, None)
            )
        return game_id

    def end_game(self, game_id: str, winner_id: Optional[str], state: dict):
        with self._conn() as conn:
            conn.execute(
                "UPDATE games SET winner_id=?, ended_at=?, state=? WHERE id=?",
                (winner_id, datetime.utcnow().isoformat(), json.dumps(state), game_id)
            )

    def record_dart(self, game_id: str, player_id: str, turn: int, dart_num: int,
                    segment: int, ring: str, score: int):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO darts VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), game_id, player_id, turn, dart_num,
                 segment, ring, score, datetime.utcnow().isoformat())
            )

    def record_override(self, game_id: str, player_id: str,
                        old_score: int, new_score: int, reason: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO overrides VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), game_id, player_id, old_score,
                 new_score, reason, datetime.utcnow().isoformat())
            )

    def get_game_history(self, limit: int = 20, player_id: Optional[str] = None) -> list:
        with self._conn() as conn:
            if player_id:
                rows = conn.execute("""
                    SELECT g.*, p.name as winner_name
                    FROM games g LEFT JOIN players p ON g.winner_id = p.id
                    WHERE g.player_ids LIKE ? AND g.ended_at IS NOT NULL
                    ORDER BY g.started_at DESC LIMIT ?
                """, (f'%{player_id}%', limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT g.*, p.name as winner_name
                    FROM games g LEFT JOIN players p ON g.winner_id = p.id
                    WHERE g.ended_at IS NOT NULL
                    ORDER BY g.started_at DESC LIMIT ?
                """, (limit,)).fetchall()
            results = []
            for row in rows:
                d = dict(row)
                d["player_ids"] = json.loads(d["player_ids"])
                d["options"] = json.loads(d["options"])
                results.append(d)
            return results

    def get_game_detail(self, game_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
            if not row:
                return None
            game = dict(row)
            game["player_ids"] = json.loads(game["player_ids"])
            game["options"] = json.loads(game["options"])
            if game["state"]:
                game["state"] = json.loads(game["state"])
            darts = conn.execute(
                "SELECT * FROM darts WHERE game_id=? ORDER BY turn_number, dart_number",
                (game_id,)
            ).fetchall()
            game["darts"] = [dict(d) for d in darts]
            return game

    # ── Live state persistence ────────────────────────────────────────────────

    def save_live_state(self, state: dict):
        """Persist the current game state so it survives server restarts."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO live_state (id, state_json, saved_at) VALUES (1, ?, ?)",
                (json.dumps(state), datetime.utcnow().isoformat())
            )

    def load_live_state(self) -> Optional[dict]:
        """Load persisted game state on startup."""
        with self._conn() as conn:
            row = conn.execute("SELECT state_json FROM live_state WHERE id=1").fetchone()
            if row:
                return json.loads(row[0])
            return None

    def clear_live_state(self):
        """Clear persisted state when a game ends or is explicitly cleared."""
        with self._conn() as conn:
            conn.execute("DELETE FROM live_state WHERE id=1")
