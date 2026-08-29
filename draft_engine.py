"""Shared snake-draft state used by the GUI (and the text simulator helpers)."""
from __future__ import annotations

import csv
import os
import re

import draft_simulator as sim
import fantasy_draft_optimizer as opt

TIP_CANDIDATES = 8
POOL_LIMIT = 120
IDEAL_BOARD_PATH = "Ideal 1st pick.csv"
MAX_POS_IN_ADVICE = 2

SKILL_TIER_FILES = {
    "RB1": os.path.join("FantasyPros", "fantasy_football_rb1_list.csv"),
    "RB2": os.path.join("FantasyPros", "fantasy_football_rb2_list.csv"),
    "WR1": os.path.join("FantasyPros", "fantasy_football_wr1_list.csv"),
    "WR2": os.path.join("FantasyPros", "fantasy_football_wr2_list.csv"),
}
PLAYER_COL_CANDIDATES = (
    "Fantasy RB1 (Projected Starter)",
    "Projected WR1",
    "Player",
)
TEAM_COL_CANDIDATES = ("NFL Team", "Team")
TIER_ORDER = ("RB1", "RB2", "WR1", "WR2")
NAME_ALIASES = {
    "kenneth gainwell": "kenny gainwell",
    "ken walker": "kenneth walker",
    "john higgins": "jayden higgins",
    "hollywood brown": "marquise brown",
}
NFL_TEAM_TO_ABBREV = {
    "arizona cardinals": "ARI",
    "atlanta falcons": "ATL",
    "baltimore ravens": "BAL",
    "buffalo bills": "BUF",
    "carolina panthers": "CAR",
    "chicago bears": "CHI",
    "cincinnati bengals": "CIN",
    "cleveland browns": "CLE",
    "dallas cowboys": "DAL",
    "denver broncos": "DEN",
    "detroit lions": "DET",
    "green bay packers": "GB",
    "houston texans": "HOU",
    "indianapolis colts": "IND",
    "jacksonville jaguars": "JAX",
    "kansas city chiefs": "KC",
    "las vegas raiders": "LV",
    "los angeles chargers": "LAC",
    "los angeles rams": "LAR",
    "miami dolphins": "MIA",
    "minnesota vikings": "MIN",
    "new england patriots": "NE",
    "new orleans saints": "NO",
    "new york giants": "NYG",
    "new york jets": "NYJ",
    "philadelphia eagles": "PHI",
    "pittsburgh steelers": "PIT",
    "san francisco 49ers": "SF",
    "seattle seahawks": "SEA",
    "tampa bay buccaneers": "TB",
    "tennessee titans": "TEN",
    "washington commanders": "WAS",
}


def _player_column(fieldnames: list[str] | None) -> str:
    names = fieldnames or []
    for candidate in PLAYER_COL_CANDIDATES:
        if candidate in names:
            return candidate
    return names[-1] if names else "Player"


def _team_column(fieldnames: list[str] | None) -> str | None:
    names = fieldnames or []
    for candidate in TEAM_COL_CANDIDATES:
        if candidate in names:
            return candidate
    return None


def _team_abbrev(team_name: str) -> str:
    return NFL_TEAM_TO_ABBREV.get((team_name or "").strip().lower(), "")


def load_skill_tier_rows() -> dict[str, list[dict]]:
    """One row per NFL team from each RB1/RB2/WR1/WR2 depth-chart file."""
    by_tier: dict[str, list[dict]] = {tier: [] for tier in TIER_ORDER}
    for tier, path in SKILL_TIER_FILES.items():
        if not os.path.exists(path):
            print(f"  (no {path} — {tier} tracker skipped)")
            continue
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            name_col = _player_column(reader.fieldnames)
            team_col = _team_column(reader.fieldnames)
            for row in reader:
                name = (row.get(name_col) or "").strip()
                if not name:
                    continue
                team = _team_abbrev(row.get(team_col) or "") if team_col else ""
                by_tier[tier].append({"name": name, "key": canon_name(name), "team": team})
    return by_tier


def bind_skill_tier_keys(players: list) -> dict[str, set[str]]:
    """Map each depth-chart slot to a player who is actually in the ADP pool.

    Listed names are used when they exist on the board. Stale backups (or
    someone already counted as RB1/WR1) fall back to the next RB/WR on that
    NFL team by ADP, so all 32 team slots can show up in the tracker.
    """
    pool_by_key = {canon_name(p.name): p for p in players}
    by_team_pos: dict[tuple[str, str], list] = {}
    for p in players:
        if p.position not in ("RB", "WR"):
            continue
        by_team_pos.setdefault((p.team, p.position), []).append(p)
    for group in by_team_pos.values():
        group.sort(key=lambda p: p.adp)

    used: set[str] = set()
    assigned: dict[str, set[str]] = {tier: set() for tier in TIER_ORDER}
    rows = load_skill_tier_rows()
    for tier in TIER_ORDER:
        pos = "RB" if tier.startswith("RB") else "WR"
        listed = 0
        fallback = 0
        missing = []
        for row in rows[tier]:
            listed += 1
            key = row["key"]
            player = pool_by_key.get(key)
            if player is not None and key not in used:
                assigned[tier].add(key)
                used.add(key)
                continue
            found = None
            for candidate in by_team_pos.get((row["team"], pos), []):
                cand_key = canon_name(candidate.name)
                if cand_key not in used:
                    found = cand_key
                    break
            if found:
                assigned[tier].add(found)
                used.add(found)
                fallback += 1
            else:
                missing.append(f"{row['name']} ({row['team'] or '?'})")
        print(
            f"  {tier}: {len(assigned[tier])}/{listed} on the board "
            f"({listed - fallback - len(missing)} by name, {fallback} next on that NFL team)."
        )
        if missing:
            print(f"    unmatched: {', '.join(missing)}")
    return assigned


def canon_name(name: str) -> str:
    key = opt.normalize_name(name)
    return NAME_ALIASES.get(key, key)


def _strip_pos_tag(name: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


def _names_from_cell(cell: str) -> list[str]:
    names = []
    for part in (cell or "").split(","):
        cleaned = _strip_pos_tag(part)
        if cleaned:
            names.append(cleaned)
    return names


def _rounds_from_label(label: str) -> list[int]:
    nums = [int(n) for n in re.findall(r"\d+", label or "")]
    if not nums:
        return []
    if len(nums) == 1:
        return nums
    return list(range(nums[0], nums[-1] + 1))


def load_ideal_board(path: str = IDEAL_BOARD_PATH) -> dict[int, list[dict]]:
    """Round -> ranked targets from the user's cheat sheet."""
    by_round: dict[int, list[dict]] = {}
    if not os.path.exists(path):
        print(f"  (no {path} — round board skipped)")
        return by_round
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rounds = _rounds_from_label(row.get("Round") or "")
            ranked: list[dict] = []
            for rank, col in (
                (1, "Rank 1 (Top Target)"),
                (2, "Rank 2 (Next Best)"),
            ):
                for name in _names_from_cell(row.get(col) or ""):
                    ranked.append({"rank": rank, "name": name, "key": canon_name(name)})
            other_rank = 3
            for name in _names_from_cell(row.get("Other Ranked Options") or ""):
                ranked.append({"rank": other_rank, "name": name, "key": canon_name(name)})
                other_rank += 1
            seen: set[str] = set()
            unique = []
            for item in ranked:
                if item["key"] in seen:
                    continue
                seen.add(item["key"])
                unique.append(item)
            for rnd in rounds:
                by_round[rnd] = unique
    return by_round


def _rank_key(player, team, available) -> tuple:
    score = opt.pick_score(player, team, available)
    return (-score, player.adp)


def _player_value(player) -> float:
    return player.vorp if player.vorp is not None else player.value_score


def advice_score(player, team, available, rnd: int, ideal_rank: int | None) -> float:
    """VORP plus starter-balance and the user's round board — not raw VORP."""
    score = opt.pick_score(player, team, available)
    pos = player.position
    has = team.pos_count(pos)
    rb = team.pos_count("RB")
    wr = team.pos_count("WR")
    te = team.pos_count("TE")
    qb = team.pos_count("QB")

    if pos in ("RB", "WR") and has < 2:
        score += 18.0 if has == 0 else 12.0
    if pos == "WR" and wr >= 2 and rb < 2:
        score -= 16.0
    if pos == "RB" and rb >= 2 and wr < 2:
        score -= 16.0
    if pos in ("RB", "WR") and has >= 3 and (rb < 2 or wr < 2 or te < 1):
        score -= 10.0

    if pos == "TE":
        if has >= 1:
            score -= 40.0
        elif rnd <= 3:
            score -= 8.0
        elif te == 0 and rnd >= 4:
            score += 8.0
    if pos == "QB":
        if has >= 1:
            score -= 40.0
        elif rnd <= 4:
            score -= 10.0
        elif qb == 0 and rnd >= 6:
            score += 10.0

    if team.roster and team.roster[-1].position == pos and pos in ("QB", "TE"):
        score -= 22.0

    if ideal_rank is not None:
        if ideal_rank == 1:
            score += 36.0
        elif ideal_rank == 2:
            score += 26.0
        else:
            score += max(10.0, 20.0 - ideal_rank)

    return score


class DraftState:
    def __init__(self) -> None:
        self.started = False
        self.num_teams = 12
        self.user_slot = 1
        self.num_rounds = 15
        self.available: list = []
        self.teams: dict = {}
        self.order: list = []
        self.pick_index = 0
        self.history: list = []
        self.search = ""
        self.pos_filter = "ALL"
        self.selected_name: str | None = None
        self.tier_keys: dict[str, set[str]] = {tier: set() for tier in TIER_ORDER}
        self.tier_totals: dict[str, int] = {tier: 0 for tier in TIER_ORDER}
        self.ideal_board: dict[int, list[dict]] = {}

    def start(self, num_teams: int, user_slot: int, num_rounds: int) -> None:
        sim.apply_league_settings(num_teams, user_slot, num_rounds)
        players = sim.load_players()
        self.num_teams = num_teams
        self.user_slot = user_slot
        self.num_rounds = num_rounds
        self.available = sorted(players, key=lambda p: p.adp)
        self.teams = {s: opt.Team(s) for s in range(1, num_teams + 1)}
        self.order = opt.snake_order(num_teams, num_rounds)
        self.pick_index = 0
        self.history = []
        self.search = ""
        self.pos_filter = "ALL"
        self.selected_name = None
        self._bind_skill_tiers(players)
        self._bind_ideal_board(players)
        self.started = True

    def _bind_skill_tiers(self, players: list) -> None:
        self.tier_keys = bind_skill_tier_keys(players)
        self.tier_totals = {tier: len(keys) for tier, keys in self.tier_keys.items()}

    def _bind_ideal_board(self, players: list) -> None:
        self.ideal_board = load_ideal_board()
        pool_keys = {canon_name(p.name) for p in players}
        for rnd, items in self.ideal_board.items():
            matched = [item for item in items if item["key"] in pool_keys]
            missing = [item["name"] for item in items if item["key"] not in pool_keys]
            print(f"  Ideal board R{rnd}: matched {len(matched)}/{len(items)}.")
            if missing:
                print(f"    unmatched: {', '.join(missing)}")
            self.ideal_board[rnd] = matched

    def _players_in_tier(self, tier: str) -> list:
        keys = self.tier_keys.get(tier, set())
        return [p for p in self.available if canon_name(p.name) in keys]

    def ideal_targets_for_round(self, rnd: int) -> list[dict]:
        return list(self.ideal_board.get(rnd, []))

    def ideal_rank_lookup(self, rnd: int) -> dict[str, int]:
        return {item["key"]: item["rank"] for item in self.ideal_targets_for_round(rnd)}

    def ideal_board_rows(self) -> list[dict]:
        if self.done or not self.is_user_pick:
            return []
        rnd = self.current_round
        available_by_key = {canon_name(p.name): p for p in self.available}
        rows = []
        for item in self.ideal_targets_for_round(rnd):
            player = available_by_key.get(item["key"])
            vorp = ""
            if player is not None:
                vorp = f"{_player_value(player):.1f}"
            rows.append({
                "rank": item["rank"],
                "label": "Top target" if item["rank"] == 1 else (
                    "Next best" if item["rank"] == 2 else f"Option {item['rank']}"
                ),
                "sheet_name": item["name"],
                "name": player.name if player else item["name"],
                "pos": player.position if player else "",
                "team": player.team if player else "",
                "adp": f"{player.adp:.1f}" if player else "",
                "vorp": vorp,
                "available": player is not None,
            })
        return rows

    def skill_snapshot(self) -> list[dict]:
        user_team = self.teams.get(self.user_slot)
        nxt = sim.next_user_overall(
            self.overall, self.user_slot, self.num_teams, self.num_rounds
        )
        wait = (nxt - self.overall - 1) if nxt else 0
        rows = []
        for tier in TIER_ORDER:
            left = self._players_in_tier(tier)
            best = None
            if left and user_team is not None:
                best = min(left, key=lambda p: _rank_key(p, user_team, self.available))
            count = len(left)
            if count == 0:
                urgency = "gone"
            elif count <= 2 or (wait > 0 and count <= wait and not self.is_user_pick):
                urgency = "danger"
            elif count <= 6:
                urgency = "warn"
            else:
                urgency = "ok"
            note = ""
            if count == 0:
                note = "None left"
            elif self.is_user_pick and count <= 2:
                note = "Last chance this tier"
            elif not self.is_user_pick and wait > 0 and count <= wait:
                note = f"May not last {wait} picks until you"
            elif count <= 6:
                note = "Getting thin"
            rows.append({
                "tier": tier,
                "left": count,
                "total": self.tier_totals.get(tier, 0),
                "best": best,
                "urgency": urgency,
                "note": note,
            })
        return rows

    @property
    def done(self) -> bool:
        return self.started and self.pick_index >= len(self.order)

    @property
    def overall(self) -> int:
        return self.pick_index + 1

    @property
    def current_round(self) -> int:
        if not self.started or self.done:
            return self.num_rounds
        return self.order[self.pick_index][0]

    @property
    def current_slot(self) -> int:
        if not self.started or self.done:
            return self.user_slot
        return self.order[self.pick_index][1]

    @property
    def is_user_pick(self) -> bool:
        return (not self.done) and self.current_slot == self.user_slot

    def player_at(self, slot: int, rnd: int):
        roster = self.teams[slot].roster
        if rnd - 1 < len(roster):
            return roster[rnd - 1]
        return None

    def draft(self, name: str) -> str | None:
        if not self.started:
            return "Start a draft first."
        if self.done:
            return "The draft is over."
        player = next((p for p in self.available if p.name == name), None)
        if player is None:
            return "That player is already gone."
        rnd, slot = self.order[self.pick_index]
        self.available.remove(player)
        self.teams[slot].roster.append(player)
        self.history.append((self.pick_index, slot, player))
        self.pick_index += 1
        self.selected_name = None
        return None

    def undo(self) -> str | None:
        if not self.history:
            return "Nothing to undo."
        prev_index, slot, player = self.history.pop()
        self.teams[slot].roster.remove(player)
        self.available.append(player)
        self.available.sort(key=lambda p: p.adp)
        self.pick_index = prev_index
        self.selected_name = None
        return None

    def _pool_match(self, player) -> bool:
        query = self.search.lower().strip()
        pos = self.pos_filter
        if pos != "ALL" and player.position != pos:
            return False
        if query and query not in player.name.lower() and query not in player.team.lower():
            return False
        return True

    def filtered_pool(self) -> list:
        matches = [p for p in self.available if self._pool_match(p)]
        if self.is_user_pick:
            ranks = self.ideal_rank_lookup(self.current_round)
            pinned = [p for p in matches if canon_name(p.name) in ranks]
            pinned.sort(key=lambda p: (ranks[canon_name(p.name)], p.adp))
            rest = [p for p in matches if canon_name(p.name) not in ranks]
            matches = pinned + rest
        return matches[:POOL_LIMIT]

    def pool_rows(self) -> list[dict]:
        ranks = self.ideal_rank_lookup(self.current_round) if self.is_user_pick else {}
        rows = []
        for p in self.filtered_pool():
            vorp = f"{p.vorp:.1f}" if p.vorp is not None else f"{p.value_score:.1f}"
            rows.append({
                "draft": "",
                "name": p.name,
                "pos": p.position,
                "team": p.team,
                "bye": p.bye or "—",
                "adp": f"{p.adp:.1f}",
                "vorp": vorp,
                "on_board": canon_name(p.name) in ranks,
            })
        return rows

    def recommendation_rows(self) -> list[dict]:
        if self.done or not self.available:
            return []
        team = self.teams[self.current_slot]
        rnd = self.current_round
        ranks = self.ideal_rank_lookup(rnd) if self.is_user_pick else {}
        eligible = [p for p in self.available if opt.eligible_for_team(p, team, rnd)]
        pool = eligible or list(self.available)

        def score_of(player) -> float:
            return advice_score(
                player, team, self.available, rnd, ranks.get(canon_name(player.name))
            )

        scored = sorted(pool, key=lambda p: (-score_of(p), p.adp))
        show = []
        pos_counts: dict[str, int] = {}
        pos_cap = {"QB": 1, "TE": 1, "DST": 1, "K": 1}
        for p in scored:
            on_board = canon_name(p.name) in ranks
            cap = pos_cap.get(p.position, MAX_POS_IN_ADVICE)
            if not on_board and pos_counts.get(p.position, 0) >= cap:
                continue
            show.append(p)
            pos_counts[p.position] = pos_counts.get(p.position, 0) + 1
            if len(show) >= TIP_CANDIDATES:
                break
        if len(show) < TIP_CANDIDATES:
            for p in scored:
                if p in show:
                    continue
                show.append(p)
                if len(show) >= TIP_CANDIDATES:
                    break
        rec_name = show[0].name if show else ""
        rows = []
        for p in show:
            vorp = f"{p.vorp:.1f}" if p.vorp is not None else f"{p.value_score:.1f}"
            rows.append({
                "name": p.name,
                "pos": p.position,
                "team": p.team,
                "adp": f"{p.adp:.1f}",
                "vorp": vorp,
                "score": f"{score_of(p):.1f}",
                "is_rec": p.name == rec_name,
                "on_board": canon_name(p.name) in ranks,
            })
        return rows

    def strategy_notes(self) -> list[str]:
        if self.done:
            return ["Draft complete. Review rosters below."]
        team = self.teams[self.user_slot]
        notes = sim.infer_strategy(team, self.current_round)
        rb, wr, te, qb = (
            team.pos_count("RB"),
            team.pos_count("WR"),
            team.pos_count("TE"),
            team.pos_count("QB"),
        )
        holes = []
        if rb < 2:
            holes.append(f"RB ({rb}/2)")
        if wr < 2:
            holes.append(f"WR ({wr}/2)")
        if te < 1 and self.current_round >= 4:
            holes.append("TE")
        if qb < 1 and self.current_round >= 6:
            holes.append("QB")
        if holes:
            notes.insert(0, "Balance first: still need " + ", ".join(holes) + ".")
        else:
            notes.insert(0, "Starters are covered. Take the best leftover value, not a third TE/QB.")
        board = self.ideal_targets_for_round(self.current_round)
        if self.is_user_pick and board:
            left = [item["name"] for item in board if any(
                canon_name(p.name) == item["key"] for p in self.available
            )]
            if left:
                notes.insert(0, f"Your round {self.current_round} board still has: {', '.join(left[:5])}.")
        return notes

    def clock_subtitle(self) -> str:
        if self.done:
            return "Draft complete"
        nxt = sim.next_user_overall(
            self.overall, self.user_slot, self.num_teams, self.num_rounds
        )
        if self.is_user_pick:
            if nxt:
                wait = nxt - self.overall - 1
                return f"Your pick. You are back on the clock in {wait} picks (overall {nxt})."
            return "Your pick — last selection of the draft."
        return f"Picking for Team {self.current_slot}. Click a player to assign this pick."

    def at_risk_names(self) -> list[str]:
        nxt = sim.next_user_overall(
            self.overall, self.user_slot, self.num_teams, self.num_rounds
        )
        return [p.name for p in sim.likely_gone_before_next(self.available, nxt)]

    def scarcity_notes(self) -> list[str]:
        notes = []
        user = self.teams.get(self.user_slot)
        if user is None:
            return notes
        snap = {row["tier"]: row for row in self.skill_snapshot()}
        rb_need = max(0, 2 - user.pos_count("RB"))
        wr_need = max(0, 2 - user.pos_count("WR"))
        rb1, rb2 = snap["RB1"], snap["RB2"]
        wr1, wr2 = snap["WR1"], snap["WR2"]
        if rb_need and rb1["left"] + rb2["left"] <= rb_need + 1:
            notes.append(
                f"RB depth is almost gone ({rb1['left']} RB1 / {rb2['left']} RB2 left) "
                f"and you still need {rb_need} RB starter(s)."
            )
        elif rb_need and rb1["left"] <= 3:
            notes.append(f"Only {rb1['left']} RB1(s) left. If you still need a lead back, spend this pick.")
        if wr_need and wr1["left"] + wr2["left"] <= wr_need + 1:
            notes.append(
                f"WR depth is almost gone ({wr1['left']} WR1 / {wr2['left']} WR2 left) "
                f"and you still need {wr_need} WR starter(s)."
            )
        elif wr_need and wr1["left"] <= 3:
            notes.append(f"Only {wr1['left']} WR1(s) left. Don't let the last starters walk.")
        return notes
