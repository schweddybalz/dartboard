"""
X01 – Count down from starting score (301/501/701/901) to exactly zero.
Supports teams: all players on a team share one score pool.
"""
from modes.base import BaseMode

# Full checkout table for all finishable scores 2–170
CHECKOUTS = {
    170:"T20 T20 Bull", 167:"T20 T19 Bull", 164:"T20 T18 Bull", 161:"T20 T17 Bull",
    160:"T20 T20 D20",  158:"T20 T20 D19",  157:"T20 T19 D20",  156:"T20 T20 D18",
    155:"T20 T19 D19",  154:"T20 T18 D20",  153:"T20 T19 D18",  152:"T20 T20 D16",
    151:"T20 T17 D20",  150:"T20 T18 D18",  149:"T20 T19 D16",  148:"T20 T16 D20",
    147:"T20 T17 D18",  146:"T20 T18 D16",  145:"T20 T15 D20",  144:"T20 T20 D12",
    143:"T20 T17 D16",  142:"T20 T14 D20",  141:"T20 T19 D12",  140:"T20 T16 D16",
    139:"T20 T13 D20",  138:"T20 T18 D12",  137:"T20 T19 D10",  136:"T20 T20 D8",
    135:"T20 T17 D12",  134:"T20 T14 D16",  133:"T20 T19 D8",   132:"T20 T16 D12",
    131:"T20 T13 D16",  130:"T20 T18 D8",   129:"T19 T16 D12",  128:"T18 T14 D16",
    127:"T20 T17 D8",   126:"T19 T19 D6",   125:"T20 T15 D8",   124:"T20 T14 D11",
    123:"T19 T16 D9",   122:"T18 T18 D7",   121:"T20 T11 D14",  120:"T20 S20 D20",
    119:"T19 T12 D13",  118:"T20 S18 D20",  117:"T20 S17 D20",  116:"T20 S16 D20",
    115:"T20 S15 D20",  114:"T20 S14 D20",  113:"T20 S13 D20",  112:"T20 S12 D20",
    111:"T20 S11 D20",  110:"T20 D25",      109:"T20 S9 D20",   108:"T20 S8 D20",
    107:"T19 D25",      106:"T20 S6 D20",   105:"T20 S5 D20",   104:"T20 S4 D20",
    103:"T20 S3 D20",   102:"T20 S2 D20",   101:"T17 D25",      100:"T20 D20",
    99: "T19 D21",       98:"T20 D19",        97:"T19 D20",       96:"T20 D18",
    95: "T19 D19",       94:"T18 D20",        93:"T19 D18",       92:"T20 D16",
    91: "T17 D20",       90:"T18 D18",        89:"T19 D16",       88:"T20 D14",
    87: "T17 D18",       86:"T18 D16",        85:"T15 D20",       84:"T20 D12",
    83: "T17 D16",       82:"T14 D20",        81:"T19 D12",       80:"T20 D10",
    79: "T13 D20",       78:"T18 D12",        77:"T19 D10",       76:"T20 D8",
    75: "T17 D12",       74:"T14 D16",        73:"T19 D8",        72:"T16 D12",
    71: "T13 D16",       70:"T18 D8",         69:"T11 D18",       68:"T20 D4",
    67: "T17 D8",        66:"T10 D18",        65:"T19 D4",        64:"T16 D8",
    63: "T13 D12",       62:"T10 D16",        61:"T15 D8",        60:"S20 D20",
    59: "S19 D20",       58:"S18 D20",        57:"S17 D20",       56:"S16 D20",
    55: "S15 D20",       54:"S14 D20",        53:"S13 D20",       52:"S12 D20",
    51: "S11 D20",       50:"Bull",           49:"S9 D20",        48:"S8 D20",
    47: "S7 D20",        46:"S6 D20",         45:"S5 D20",        44:"S4 D20",
    43: "S3 D20",        42:"S2 D20",         41:"S1 D20",        40:"D20",
    39: "S7 D16",        38:"D19",            37:"S5 D16",        36:"D18",
    35: "S3 D16",        34:"D17",            33:"S1 D16",        32:"D16",
    31: "S7 D12",        30:"D15",            29:"S5 D12",        28:"D14",
    27: "S3 D12",        26:"D13",            25:"S9 D8",         24:"D12",
    23: "S7 D8",         22:"D11",            21:"S5 D8",         20:"D10",
    19: "S3 D8",         18:"D9",             17:"S1 D8",         16:"D8",
    15: "S7 D4",         14:"D7",             13:"S5 D4",         12:"D6",
    11: "S3 D4",         10:"D5",              9:"S1 D4",          8:"D4",
     7: "S3 D2",          6:"D3",              5:"S1 D2",          4:"D2",
     3: "S1 D1",          2:"D1",
}

# Easy checkout table (no double-out required, ≤3 darts)
CHECKOUTS_EASY = {
    1:  "1",
    2:  "2",   3:  "3",   4:  "4",   5:  "5",   6:  "6",   7:  "7",
    8:  "8",   9:  "9",  10: "10",  11: "11",  12: "12",  13: "13",
    14: "14",  15: "15",  16: "16",  17: "17",  18: "18",  19: "19",
    20: "20",
    21: "20 1",   22: "20 2",   23: "20 3",   24: "20 4",   25: "SB",
    26: "20 6",   27: "20 7",   28: "20 8",   29: "20 9",   30: "20 10",
    31: "20 11",  32: "20 12",  33: "20 13",  34: "20 14",  35: "20 15",
    36: "20 16",  37: "20 17",  38: "20 18",  39: "20 19",  40: "20 20",
    41: "20 20 1",  42: "20 20 2",  43: "20 20 3",  44: "20 20 4",
    45: "25 20",    46: "20 20 6",  47: "20 20 7",  48: "20 20 8",
    49: "20 20 9",  50: "Bull",
    51: "20 20 11", 52: "20 20 12", 53: "20 20 13", 54: "20 20 14",
    55: "25 20 10", 56: "20 20 16", 57: "20 20 17", 58: "20 20 18",
    59: "20 20 19", 60: "T20",
    61: "T20 1",   62: "T20 2",   63: "T20 3",   64: "T20 4",   65: "T20 5",
    66: "T20 6",   67: "T20 7",   68: "T20 8",   69: "T20 9",   70: "T20 10",
    71: "T20 11",  72: "T20 12",  73: "T20 13",  74: "T20 14",  75: "T20 15",
    76: "T20 16",  77: "T20 17",  78: "T20 18",  79: "T20 19",  80: "T20 20",
    81: "T20 20 1",  82: "T20 20 2",  83: "T20 20 3",  84: "T20 20 4",
    85: "T20 25",    86: "T20 20 6",  87: "T20 20 7",  88: "T20 20 8",
    89: "T20 20 9",  90: "T20 20 10", 91: "T20 20 11", 92: "T20 20 12",
    93: "T20 20 13", 94: "T20 20 14", 95: "T20 15 20", 96: "T20 20 16",
    97: "T20 20 17", 98: "T20 20 18", 99: "T20 20 19", 100:"T20 20 20",
    101:"T20 T13 2",   102:"T20 T14",     103:"T20 T14 1",   104:"T20 T14 2",
    105:"T20 T15",     106:"T20 T15 1",   107:"T20 T15 2",   108:"T20 T16",
    109:"T20 T16 1",   110:"T20 T16 2",   111:"T20 T17",     112:"T20 T17 1",
    113:"T20 T17 2",   114:"T20 T18",     115:"T20 T18 1",   116:"T20 T18 2",
    117:"T20 T19",     118:"T20 T19 1",   119:"T20 T19 2",   120:"T20 T20",
    121:"T20 T20 1",   122:"T20 T20 2",   123:"T20 T20 3",   124:"T20 T20 4",
    125:"T20 T20 5",   126:"T20 T20 6",   127:"T20 T20 7",   128:"T20 T20 8",
    129:"T20 T20 9",   130:"T20 T20 10",  131:"T20 T20 11",  132:"T20 T20 12",
    133:"T20 T20 13",  134:"T20 T20 14",  135:"T20 T20 15",  136:"T20 T20 16",
    137:"T20 T20 17",  138:"T20 T20 18",  139:"T20 T20 19",  140:"T20 T20 20",
}

# Full checkout table for double-out (2–170)
CHECKOUTS = {
    170:"T20 T20 Bull", 167:"T20 T19 Bull", 164:"T20 T18 Bull", 161:"T20 T17 Bull",
    160:"T20 T20 D20",  158:"T20 T20 D19",  157:"T20 T19 D20",  156:"T20 T20 D18",
    155:"T20 T19 D19",  154:"T20 T18 D20",  153:"T20 T19 D18",  152:"T20 T20 D16",
    151:"T20 T17 D20",  150:"T20 T18 D18",  149:"T20 T19 D16",  148:"T20 T16 D20",
    147:"T20 T17 D18",  146:"T20 T18 D16",  145:"T20 T15 D20",  144:"T20 T20 D12",
    143:"T20 T17 D16",  142:"T20 T14 D20",  141:"T20 T19 D12",  140:"T20 T16 D16",
    139:"T20 T13 D20",  138:"T20 T18 D12",  137:"T20 T19 D10",  136:"T20 T20 D8",
    135:"T20 T17 D12",  134:"T20 T14 D16",  133:"T20 T19 D8",   132:"T20 T16 D12",
    131:"T20 T13 D16",  130:"T20 T18 D8",   129:"T19 T16 D12",  128:"T18 T14 D16",
    127:"T20 T17 D8",   126:"T19 T19 D6",   125:"T20 T15 D8",   124:"T20 T14 D11",
    123:"T19 T16 D9",   122:"T18 T18 D7",   121:"T20 T11 D14",  120:"T20 S20 D20",
    119:"T19 T12 D13",  118:"T20 S18 D20",  117:"T20 S17 D20",  116:"T20 S16 D20",
    115:"T20 S15 D20",  114:"T20 S14 D20",  113:"T20 S13 D20",  112:"T20 S12 D20",
    111:"T20 S11 D20",  110:"T20 D25",      109:"T20 S9 D20",   108:"T20 S8 D20",
    107:"T19 D25",      106:"T20 S6 D20",   105:"T20 S5 D20",   104:"T20 S4 D20",
    103:"T20 S3 D20",   102:"T20 S2 D20",   101:"T17 D25",      100:"T20 D20",
    99: "T19 D21",       98:"T20 D19",        97:"T19 D20",       96:"T20 D18",
    95: "T19 D19",       94:"T18 D20",        93:"T19 D18",       92:"T20 D16",
    91: "T17 D20",       90:"T18 D18",        89:"T19 D16",       88:"T20 D14",
    87: "T17 D18",       86:"T18 D16",        85:"T15 D20",       84:"T20 D12",
    83: "T17 D16",       82:"T14 D20",        81:"T19 D12",       80:"T20 D10",
    79: "T13 D20",       78:"T18 D12",        77:"T19 D10",       76:"T20 D8",
    75: "T17 D12",       74:"T14 D16",        73:"T19 D8",        72:"T16 D12",
    71: "T13 D16",       70:"T18 D8",         69:"T11 D18",       68:"T20 D4",
    67: "T17 D8",        66:"T10 D18",        65:"T19 D4",        64:"T16 D8",
    63: "T13 D12",       62:"T10 D16",        61:"T15 D8",        60:"S20 D20",
    59: "S19 D20",       58:"S18 D20",        57:"S17 D20",       56:"S16 D20",
    55: "S15 D20",       54:"S14 D20",        53:"S13 D20",       52:"S12 D20",
    51: "S11 D20",       50:"Bull",           49:"S9 D20",        48:"S8 D20",
    47: "S7 D20",        46:"S6 D20",         45:"S5 D20",        44:"S4 D20",
    43: "S3 D20",        42:"S2 D20",         41:"S1 D20",        40:"D20",
    39: "S7 D16",        38:"D19",            37:"S5 D16",        36:"D18",
    35: "S3 D16",        34:"D17",            33:"S1 D16",        32:"D16",
    31: "S7 D12",        30:"D15",            29:"S5 D12",        28:"D14",
    27: "S3 D12",        26:"D13",            25:"S9 D8",         24:"D12",
    23: "S7 D8",         22:"D11",            21:"S5 D8",         20:"D10",
    19: "S3 D8",         18:"D9",             17:"S1 D8",         16:"D8",
    15: "S7 D4",         14:"D7",             13:"S5 D4",         12:"D6",
    11: "S3 D4",         10:"D5",              9:"S1 D4",          8:"D4",
     7: "S3 D2",          6:"D3",              5:"S1 D2",          4:"D2",
     3: "S1 D1",          2:"D1",
}


def _parse_teams(teams_str, players):
    """Parse '1,2|3,4' → [[pid0,pid1],[pid2,pid3]], or None."""
    if not teams_str or not teams_str.strip():
        return None
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


class X01Mode(BaseMode):
    mode_id = "x01"
    mode_name = "X01"
    description = "Count down from 301, 501, 701, or 901 to exactly zero. Supports teams."
    options_schema = {
        "start_score": {"type": "integer", "default": 301, "options": [301, 501, 701, 901]},
        "double_out":  {"type": "boolean", "default": False},
        "double_in":   {"type": "boolean", "default": False},
        "teams": {"type": "string", "default": "",
                  "description": "Optional team groupings e.g. '1,2|3,4' (use player position numbers)"},
        "team_names": {"type": "string", "default": "",
                       "description": "Optional team names e.g. 'Reds|Blues'"},
    }

    def __init__(self, players, options):
        super().__init__(players, options)
        self.start = options.get("start_score", 301)
        self.double_out = options.get("double_out", False)
        self.double_in = options.get("double_in", False)

        # Teams
        self._teams = _parse_teams(options.get("teams", ""), players)
        names_str = options.get("team_names", "").strip()
        if names_str and self._teams:
            raw = [n.strip() for n in names_str.split("|")]
            self._team_names = [raw[i] if i < len(raw) and raw[i] else f"Team {i+1}"
                                for i in range(len(self._teams))]
        else:
            self._team_names = [f"Team {i+1}" for i in range(len(self._teams or []))]

        colors_str = options.get("team_colors", "").strip()
        if colors_str and self._teams:
            raw_colors = [c.strip() for c in colors_str.split("|")]
            self._team_colors = [raw_colors[i] if i < len(raw_colors) and raw_colors[i] else None
                                 for i in range(len(self._teams))]
        else:
            self._team_colors = [None] * len(self._teams or [])

        # Turn order for teams: cycle through teams evenly (T0,T1,T2,T3,T0,T1,T2,T3...)
        # Within each team, players rotate each time their team comes up.
        if self._teams:
            max_len = max(len(t) for t in self._teams)
            n_teams = len(self._teams)
            # player_order just groups players by team for engine reordering
            ordered = []
            for team in self._teams:
                ordered.extend(team)
            self.player_order = ordered
            # Track which member of each team throws next
            self._team_next_member = [0] * n_teams
            # Turn sequence: n_teams entries per round, max_len rounds
            self._team_sequence = [ti for _ in range(max_len) for ti in range(n_teams)]
            self._team_turn_idx = 0  # index into _team_sequence

        self._opened = {p["id"]: not self.double_in for p in players}
        self._turn_start_score = {}

    def _current_team_player(self, state):
        if not self._teams:
            return None, None
        seq_idx = self._team_turn_idx % len(self._team_sequence)
        team_idx = self._team_sequence[seq_idx]
        team = self._teams[team_idx]
        member_idx = self._team_next_member[team_idx] % len(team)
        pid = team[member_idx]
        return team_idx, pid

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

    def _team_of(self, pid):
        """Return team index for a player id, or None."""
        if not self._teams:
            return None
        for i, team in enumerate(self._teams):
            if pid in team:
                return i
        return None

    def _team_score(self, scores, team_idx):
        """Shared score for a team = score stored on first player (representative)."""
        return scores[self._teams[team_idx][0]]

    def initial_scores(self):
        if self._teams:
            # All players on a team share one score; store on first player, rest = 0
            scores = {}
            for i, team in enumerate(self._teams):
                for j, pid in enumerate(team):
                    scores[pid] = self.start if j == 0 else 0
        else:
            scores = {p["id"]: self.start for p in self.players}
        self._turn_start_score = dict(scores)
        return scores

    def _rep(self, pid):
        """Representative player id for scoring (first member of team, or self)."""
        ti = self._team_of(pid)
        return self._teams[ti][0] if ti is not None else pid

    def _checkout_table(self):
        return CHECKOUTS if self.double_out else CHECKOUTS_EASY

    def on_dart(self, state, player, segment, ring, raw_score):
        scores = dict(state["player_scores"])
        pid = player["id"]
        rep = self._rep(pid)
        current = scores[rep]

        dart_num = len(state.get("darts_this_turn", []))
        if dart_num == 0:
            self._turn_start_score[rep] = current

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

        new_score = current - raw_score
        turn_start = self._turn_start_score.get(rep, current)

        # Bust
        if new_score < 0 or (new_score == 1 and self.double_out):
            scores[rep] = turn_start
            return {
                "player_scores": scores,
                "scored": 0,
                "bust": True,
                "advance_turn": True,
                "message": f"Bust! Back to {turn_start}",
            }

        if new_score == 0:
            if self.double_out and ring not in ("double", "bullseye"):
                scores[rep] = turn_start
                return {
                    "player_scores": scores,
                    "scored": 0,
                    "bust": True,
                    "advance_turn": True,
                    "message": "Need a double to finish! Bust.",
                    "announcement": f"{player['name']} needs a double to finish!",
                }
            scores[rep] = 0
            return {
                "player_scores": scores,
                "scored": raw_score,
                "winner_id": pid,
                "advance_turn": True,
                "message": f"{player['name']} wins!",
                "announcement": f"Game shot! {player['name']} wins!",
            }

        scores[rep] = new_score
        checkout = self._checkout_table().get(new_score, "")
        return {
            "player_scores": scores,
            "scored": raw_score,
            "message": f"{new_score} remaining" + (f" — {checkout}" if checkout else ""),
            "announcement": f"{raw_score}. {new_score} left." + (f" Checkout: {checkout}" if checkout else ""),
        }

    def is_game_over(self, state):
        scores = state["player_scores"]
        if self._teams:
            return any(scores[team[0]] == 0 for team in self._teams)
        return any(v == 0 for v in scores.values())

    def get_display_state(self, state):
        scores = state["player_scores"]
        if self._teams:
            team_info = [
                {
                    "team_id": f"team_{i}",
                    "name": self._team_names[i] if i < len(self._team_names) else f"Team {i+1}",
                    "color": self._team_colors[i] if i < len(self._team_colors) else None,
                    "player_ids": team,
                    "score": scores[team[0]],
                    "checkout": self._checkout_table().get(scores[team[0]], ""),
                }
                for i, team in enumerate(self._teams)
            ]
        else:
            team_info = None
        # Achievement from current 3-dart turn
        achievement = None
        darts = state.get("darts_this_turn", [])
        if len(darts) == 3:
            turn_score = sum(d.get("scored", 0) for d in darts)
            rings = [d.get("ring", "") for d in darts]
            segs  = [d.get("segment", 0) for d in darts]
            if turn_score == 180:
                achievement = "maximum"
            elif all(r in ("bull", "bullseye") for r in rings):
                achievement = "hat_trick"
            elif len(set(segs)) == 1 and len(set(rings)) == 1 and rings[0] not in ('miss',):
                achievement = "three_in_a_bed"
            elif turn_score >= 140:
                achievement = "high_ton"
            elif turn_score >= 100:
                achievement = "low_ton"

        return {
            "start_score": self.start,
            "double_out": self.double_out,
            "double_in": self.double_in,
            "remaining": {pid: scores[self._rep(pid)] for pid in scores},
            "checkouts": {pid: self._checkout_table().get(scores[self._rep(pid)], "") for pid in scores},
            "teams": team_info,
            "achievement": achievement,
        }

    def restore_state(self, state):
        self._opened = {p["id"]: not self.double_in for p in state["players"]}
        self._turn_start_score = dict(state.get("player_scores", {}))

    def sync_scores(self, scores):
        pass


MODE_CLASS = X01Mode
