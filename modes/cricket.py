"""
Cricket – Close 15–20 and bull. Score points on open numbers.
Supports teams (e.g. 2v2, 2v2v2). Marks displayed as three bars per number.
"""
from modes.base import BaseMode

CRICKET_NUMBERS = [20, 19, 18, 17, 16, 15, 25]  # display order top-to-bottom


class CricketMode(BaseMode):
    mode_id = "cricket"
    mode_name = "Cricket"
    description = "Close 15–20 and Bull. Score on open numbers. Supports teams."
    options_schema = {
        "cutthroat": {"type": "boolean", "default": False,
                      "description": "Points go to opponents instead of yourself"},
        "teams": {"type": "string", "default": "",
                  "description": "Optional team groupings e.g. '1,2|3,4' for 2v2 (use player position numbers)"},
        "team_names": {"type": "string", "default": "",
                       "description": "Optional team names e.g. 'Reds|Blues'"},
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.cutthroat = options.get("cutthroat", False)
        # Parse teams: "1,2|3,4" → [[pid0,pid1],[pid2,pid3]]
        self._teams = self._parse_teams(options.get("teams", ""), players)
        # Parse team names: "Reds|Blues"
        names_str = options.get("team_names", "").strip()
        if names_str and self._teams:
            raw = [n.strip() for n in names_str.split("|")]
            self._team_names = [raw[i] if i < len(raw) and raw[i] else f"Team {i+1}"
                                for i in range(len(self._teams))]
        else:
            self._team_names = [f"Team {i+1}" for i in range(len(self._teams or []))]
        # marks[entity_id][number] = 0..3  (entity = player or team)
        self._marks = self._fresh_marks()
        self._points = {e: 0 for e in self._entity_ids()}

        # Turn order for teams: cycle teams evenly, rotate players within each team
        if self._teams:
            max_len = max(len(t) for t in self._teams)
            n_teams = len(self._teams)
            ordered = []
            for team in self._teams:
                ordered.extend(team)
            self.player_order = ordered
            self._team_next_member = [0] * n_teams
            self._team_sequence = [ti for _ in range(max_len) for ti in range(n_teams)]
            self._team_turn_idx = 0

    def _current_team_player(self, state):
        if not self._teams:
            return None, None
        seq_idx = self._team_turn_idx % len(self._team_sequence)
        team_idx = self._team_sequence[seq_idx]
        team = self._teams[team_idx]
        member_idx = self._team_next_member[team_idx] % len(team)
        return team_idx, team[member_idx]

    def on_turn_start(self, state):
        if not self._teams:
            return
        team_idx, pid = self._current_team_player(state)
        for i, p in enumerate(state["players"]):
            if p["id"] == pid:
                state["current_player_idx"] = i
                break

    def advance_team_turn(self):
        if not self._teams:
            return
        seq_idx = self._team_turn_idx % len(self._team_sequence)
        team_idx = self._team_sequence[seq_idx]
        self._team_next_member[team_idx] = (self._team_next_member[team_idx] + 1) % len(self._teams[team_idx])
        self._team_turn_idx += 1

    def _parse_teams(self, teams_str, players):
        """Parse team string into list of lists of player ids."""
        if not teams_str or not teams_str.strip():
            return None  # No teams — individual play
        try:
            groups = []
            for group in teams_str.split("|"):
                indices = [int(x.strip()) - 1 for x in group.split(",")]
                pids = [players[i]["id"] for i in indices if 0 <= i < len(players)]
                if pids:
                    groups.append(pids)
            return groups if len(groups) >= 2 else None
        except Exception:
            return None

    def _entity_ids(self):
        """Return scoring entity IDs — team indices as strings or player IDs."""
        if self._teams:
            return [f"team_{i}" for i in range(len(self._teams))]
        return [p["id"] for p in self.players]

    def _entity_for_player(self, pid):
        if self._teams:
            for i, team in enumerate(self._teams):
                if pid in team:
                    return f"team_{i}"
        return pid

    def _fresh_marks(self):
        return {eid: {n: 0 for n in CRICKET_NUMBERS} for eid in self._entity_ids()}

    def initial_scores(self):
        return {p["id"]: 0 for p in self.players}

    def on_dart(self, state, player, segment, ring, raw_score):
        pid = player["id"]
        eid = self._entity_for_player(pid)

        if ring in ("bull", "bullseye"):
            number = 25
            hits = 1 if ring == "bull" else 2
        elif segment in CRICKET_NUMBERS:
            number = segment
            hits = {"single": 1, "double": 2, "triple": 3}.get(ring, 0)
        else:
            return {
                "player_scores": dict(state["player_scores"]),
                "scored": 0,
                "message": f"{segment} not a cricket number",
            }

        if hits == 0:
            return {"player_scores": dict(state["player_scores"]), "scored": 0}

        marks = self._marks
        current_marks = marks[eid][number]
        new_marks = min(current_marks + hits, 3)
        overflow_hits = max(0, current_marks + hits - 3)
        marks[eid][number] = new_marks

        scored_points = 0
        scores = dict(state["player_scores"])

        if overflow_hits > 0 and marks[eid][number] >= 3:
            point_value = 25 if number == 25 else number
            # Find entities that haven't closed this number
            other_eids = [e for e in self._entity_ids() if e != eid and marks[e][number] < 3]
            if other_eids:
                scored_points = overflow_hits * point_value
                if self.cutthroat:
                    # Add points to opponent entities — credit only first player per team
                    for oe in other_eids:
                        target_pids = self._teams[int(oe.split("_")[1])] if self._teams else [oe]
                        scores[target_pids[0]] = scores.get(target_pids[0], 0) + scored_points
                else:
                    # Add points to current entity — in teams mode, credit only the first player
                    # to avoid double-counting when the display sums all team members
                    my_pids = self._teams[int(eid.split("_")[1])] if self._teams else [pid]
                    rep = my_pids[0]  # single representative to avoid sum() doubling
                    scores[rep] = scores.get(rep, 0) + scored_points
                    self._points[eid] = self._points.get(eid, 0) + scored_points

        state["player_scores"] = scores
        label = "Bull" if number == 25 else str(number)
        msg = f"{label}: {new_marks}/3"
        if scored_points:
            msg += f" (+{scored_points})"

        return {
            "player_scores": scores,
            "scored": scored_points,
            "message": msg,
            "announcement": self._announce(player["name"], number, new_marks, scored_points),
        }

    def _all_closed_by(self, eid):
        return all(self._marks[eid][n] >= 3 for n in CRICKET_NUMBERS)

    def is_game_over(self, state):
        scores = state["player_scores"]
        for eid in self._entity_ids():
            if self._all_closed_by(eid):
                # Get total score for this entity
                my_pids = self._teams[int(eid.split("_")[1])] if self._teams else [eid]
                my_score = sum(scores.get(p, 0) for p in my_pids)
                # Check all other entities have <= score (or >= in cutthroat)
                all_beat = True
                for oe in self._entity_ids():
                    if oe == eid:
                        continue
                    op_pids = self._teams[int(oe.split("_")[1])] if self._teams else [oe]
                    op_score = sum(scores.get(p, 0) for p in op_pids)
                    if self.cutthroat:
                        if op_score < my_score:
                            all_beat = False; break
                    else:
                        if op_score > my_score:
                            all_beat = False; break
                if all_beat:
                    # Set winner to first player of winning entity
                    state["winner_id"] = my_pids[0]
                    return True
        return False

    def get_display_state(self, state):
        # Build per-player marks by mapping through entity
        player_marks = {}
        for p in self.players:
            eid = self._entity_for_player(p["id"])
            player_marks[p["id"]] = {str(n): self._marks[eid][n] for n in CRICKET_NUMBERS}

        # Determine which numbers are globally closed (all entities have 3 marks)
        globally_closed = [
            n for n in CRICKET_NUMBERS
            if all(self._marks[eid][n] >= 3 for eid in self._entity_ids())
        ]

        # Team info for display
        team_info = None
        if self._teams:
            team_info = [
                {
                    "team_id": f"team_{i}",
                    "name": self._team_names[i] if i < len(self._team_names) else f"Team {i+1}",
                    "player_ids": team,
                    "marks": {str(n): self._marks[f"team_{i}"][n] for n in CRICKET_NUMBERS},
                    "score": sum(state["player_scores"].get(p, 0) for p in team),
                }
                for i, team in enumerate(self._teams)
            ]

        return {
            "cricket_marks": player_marks,
            "cricket_numbers": CRICKET_NUMBERS,
            "globally_closed": globally_closed,
            "cutthroat": self.cutthroat,
            "teams": team_info,
            "points": dict(state["player_scores"]),
        }

    def restore_state(self, state):
        self._marks = self._fresh_marks()
        self._points = {e: 0 for e in self._entity_ids()}

    def _announce(self, name, number, marks, points):
        label = "Bull" if number == 25 else str(number)
        if marks >= 3:
            base = f"{name} closes {label}!"
        elif marks == 2:
            base = f"{name} — 2 marks on {label}"
        else:
            base = f"{name} hits {label}"
        if points:
            base += f" — {points} points!"
        return base


MODE_CLASS = CricketMode
