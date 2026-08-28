"""Shared snake-draft state used by the GUI (and the text simulator helpers)."""
from __future__ import annotations

import draft_simulator as sim
import fantasy_draft_optimizer as opt

TIP_CANDIDATES = 8
POOL_LIMIT = 120


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
        self.started = True

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

    def filtered_pool(self) -> list:
        query = self.search.lower().strip()
        pos = self.pos_filter
        out = []
        for p in self.available:
            if pos != "ALL" and p.position != pos:
                continue
            if query and query not in p.name.lower() and query not in p.team.lower():
                continue
            out.append(p)
            if len(out) >= POOL_LIMIT:
                break
        return out

    def pool_rows(self) -> list[dict]:
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
            })
        return rows

    def recommendation_rows(self) -> list[dict]:
        if self.done or not self.available:
            return []
        team = self.teams[self.current_slot]
        rnd = self.current_round
        scored = sorted(
            self.available,
            key=lambda p: (-opt.pick_score(p, team, self.available), p.adp),
        )
        eligible = [p for p in scored if opt.eligible_for_team(p, team, rnd)]
        show = (eligible or scored)[:TIP_CANDIDATES]
        rec = opt.recommend_pick(self.available, team, rnd)
        rows = []
        for p in show:
            rows.append({
                "name": p.name,
                "pos": p.position,
                "team": p.team,
                "adp": f"{p.adp:.1f}",
                "score": f"{opt.pick_score(p, team, self.available):.1f}",
                "is_rec": p.name == rec.name,
            })
        return rows

    def strategy_notes(self) -> list[str]:
        if self.done:
            return ["Draft complete. Review rosters below."]
        team = self.teams[self.user_slot]
        return sim.infer_strategy(team, self.current_round)

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
