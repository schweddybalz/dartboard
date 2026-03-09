# 🎯 Smart Dartboard – Game Engine

FastAPI-based game engine for the smart dartboard project.  
Runs locally on a Raspberry Pi 5 (or any machine). No internet required.

---

## Quick Start

```bash
chmod +x start.sh
./start.sh
```

Then open **http://localhost:8000/docs** for the interactive API explorer.

---

## Project Structure

```
dartboard/
├── main.py           # FastAPI app, all endpoints
├── engine.py         # Game orchestration, undo, turn management
├── database.py       # SQLite layer (players, games, darts, overrides)
├── models.py         # Pydantic request models
├── modes/
│   ├── base.py           # BaseMode class – extend to add new games
│   ├── m501.py           # 501 / 301 (countdown, double out)
│   ├── cricket.py        # Cricket / Cutthroat Cricket
│   ├── around_the_clock.py  # Around the Clock
│   ├── shanghai.py       # Shanghai (instant win on S+D+T)
│   ├── killer.py         # Killer
│   └── limbo.py          # Limbo (score under the bar)
├── data/
│   └── dartboard.db  # SQLite database (auto-created)
├── uploads/          # Player avatar images
├── requirements.txt
└── start.sh
```

---

## Key API Endpoints

### Players
| Method | Path | Description |
|--------|------|-------------|
| GET | `/players` | List all players |
| POST | `/players` | Create player `{"name": "Alice"}` |
| POST | `/players/{id}/avatar` | Upload avatar image |
| GET | `/players/{id}/stats` | Lifetime stats |

### Game
| Method | Path | Description |
|--------|------|-------------|
| GET | `/modes` | List available game modes |
| POST | `/game/new` | Start a game |
| GET | `/game/state` | Current game state |
| POST | `/game/dart` | Submit a dart throw |
| POST | `/game/override` | Manually correct a score |
| POST | `/game/undo` | Undo last dart |
| POST | `/game/next-turn` | Skip to next player |
| POST | `/game/end` | End game early |

### History
| Method | Path | Description |
|--------|------|-------------|
| GET | `/history` | Recent games |
| GET | `/history/{game_id}` | Full game detail + all darts |

### WebSocket
Connect to `ws://[host]:8000/ws` for real-time events.

**Event types pushed to clients:**
- `state_sync` – full state on connect
- `game_started` – new game created
- `dart_scored` – dart processed
- `score_overridden` – manual override applied
- `dart_undone` – undo happened
- `turn_changed` – turn advanced
- `game_over` – game ended with winner
- `announcement` – text string for TTS / display

---

## Starting a Game (Example)

```bash
# 1. Create players
curl -X POST http://localhost:8000/players \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice"}'
# → {"id": "uuid-alice", ...}

curl -X POST http://localhost:8000/players \
  -H "Content-Type: application/json" \
  -d '{"name": "Bob"}'
# → {"id": "uuid-bob", ...}

# 2. Start a 501 game
curl -X POST http://localhost:8000/game/new \
  -H "Content-Type: application/json" \
  -d '{"mode": "501", "player_ids": ["uuid-alice", "uuid-bob"], "options": {"start_score": 501}}'

# 3. Throw a dart (Triple 20 = 60 points)
curl -X POST http://localhost:8000/game/dart \
  -H "Content-Type: application/json" \
  -d '{"segment": 20, "ring": "triple"}'

# 4. Override a score manually
curl -X POST http://localhost:8000/game/override \
  -H "Content-Type: application/json" \
  -d '{"player_id": "uuid-alice", "new_score": 300, "reason": "Camera missed a dart"}'
```

---

## Ring Values

| `ring` value | Meaning |
|---|---|
| `"single"` | Single segment (×1) |
| `"double"` | Double ring (×2) |
| `"triple"` | Triple ring (×3) |
| `"bull"` | Outer bull (25 pts) |
| `"bullseye"` | Inner bull (50 pts) |
| `"miss"` | Off the board (0 pts) |

---

## Adding a Custom Game Mode

Create `modes/my_game.py`:

```python
from modes.base import BaseMode

class MyGame(BaseMode):
    mode_id = "my_game"
    mode_name = "My Custom Game"
    description = "Description shown in the UI"
    options_schema = {}   # Optional: define configurable options

    def initial_scores(self):
        return {p["id"]: 0 for p in self.players}

    def on_dart(self, state, player, segment, ring, raw_score):
        scores = dict(state["player_scores"])
        scores[player["id"]] += raw_score
        return {
            "player_scores": scores,
            "scored": raw_score,
            "message": f"+{raw_score}",
        }

    def is_game_over(self, state):
        return any(v >= 100 for v in state["player_scores"].values())

    def get_display_state(self, state):
        return {"scores": state["player_scores"]}

MODE_CLASS = MyGame
```

Restart the server — the mode auto-loads and appears in `/modes`.

---

## Camera Integration

When your CV pipeline detects a dart, POST to:

```
POST /camera/dart
{"segment": 20, "ring": "triple"}
```

This is identical to `/game/dart` but semantically separate so you can
log / rate-limit camera input differently from manual overrides.

---

## WebSocket Client (JavaScript)

```javascript
const ws = new WebSocket("ws://dartboard.local:8000/ws");

ws.onmessage = (e) => {
  const { event, payload } = JSON.parse(e.data);
  if (event === "dart_scored") {
    updateScoreboard(payload);
    if (payload.announcement) speak(payload.announcement);
  }
  if (event === "game_over") showWinner(payload.winner_id);
};
```

---

## Deployment on Raspberry Pi 5

```bash
# Auto-start on boot (systemd)
sudo nano /etc/systemd/system/dartboard.service
```

```ini
[Unit]
Description=Smart Dartboard Engine
After=network.target

[Service]
WorkingDirectory=/home/pi/dartboard
ExecStart=/home/pi/dartboard/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable dartboard
sudo systemctl start dartboard
```

Access from any device on your network: `http://[pi-ip]:8000`
