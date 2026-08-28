#!/usr/bin/env python3
"""Sleeper/ESPN-style clickable draft room, built with NiceGUI."""
from __future__ import annotations

from nicegui import ui

from draft_engine import DraftState

state = DraftState()

POS_COLORS = {
    "QB": "#ef4444",
    "RB": "#22c55e",
    "WR": "#3b82f6",
    "TE": "#f59e0b",
    "DST": "#64748b",
    "K": "#a855f7",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800&display=swap');

body, .q-page, .nicegui-content {
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  background: #0b1220 !important;
  color: #e8eefc;
}
.nicegui-content { padding: 12px 16px 24px; }

.clock-bar {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  background: linear-gradient(90deg, #151c2e, #1b2340);
  border: 1px solid #2a3558; border-radius: 14px; padding: 12px 18px;
}
.clock-bar.yours { border-color: #f5c518; box-shadow: 0 0 0 1px #f5c51855; }
.clock-kicker { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: #9db0d8; }
.clock-title { font-size: 22px; font-weight: 800; letter-spacing: -0.02em; }
.clock-sub { color: #b7c4e4; font-size: 13px; margin-top: 2px; }

.board-wrap {
  overflow: auto; border-radius: 12px; border: 1px solid #243056;
  background: #10182a; max-height: 42vh;
}
.board {
  display: grid; gap: 4px; padding: 8px; min-width: max-content;
}
.team-h, .round-lbl, .cell {
  border-radius: 8px; min-height: 52px; min-width: 102px;
}
.round-lbl {
  min-width: 36px; display: flex; align-items: center; justify-content: center;
  color: #8ea0c8; font-weight: 700; font-size: 12px; background: #0e1628;
}
.team-h {
  display: flex; align-items: center; justify-content: center;
  background: #18233c; font-weight: 800; font-size: 12px; letter-spacing: 0.04em;
}
.team-h.you { background: #3b2a86; color: #f5c518; }
.cell {
  padding: 6px 7px; background: #162036; border: 1px dashed #2a3a62; color: #6f82ab;
  font-size: 11px; line-height: 1.15;
}
.cell.filled { border-style: solid; color: #0b1220; font-weight: 700; }
.cell.on-clock { border: 2px solid #f5c518; background: #2a2410; color: #f5c518; font-weight: 800; }
.cell .nm { font-size: 12px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cell .meta { opacity: 0.85; font-weight: 600; }

.pos-chip {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 36px; padding: 2px 6px; border-radius: 999px;
  font-size: 10px; font-weight: 800; color: #0b1220;
}
.side-card {
  background: #121a2d; border: 1px solid #243056; border-radius: 14px; padding: 12px;
}
.rec-card {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  background: #18233c; border-radius: 10px; padding: 8px 10px; cursor: pointer;
  border: 1px solid transparent;
}
.rec-card:hover { border-color: #f5c518; }
.rec-card.best { background: #3b2a14; border-color: #f5c518; }
.note { color: #c5d0ea; font-size: 13px; line-height: 1.35; margin: 0 0 8px; }
.muted { color: #8ea0c8; font-size: 12px; }
.player-row {
  background: #18233c; border-radius: 10px; padding: 6px 8px;
  border: 1px solid transparent; cursor: pointer;
}
.player-row:hover { border-color: #3b82f6; }
.player-row.selected { border-color: #f5c518; background: #2a2410; }
"""


def pos_style(pos: str) -> str:
    return f"background:{POS_COLORS.get(pos, '#64748b')}"


def board_markup() -> str:
    cols = state.num_teams + 1
    html = [f'<div class="board" style="grid-template-columns: 36px repeat({state.num_teams}, minmax(102px, 1fr));">']
    html.append('<div class="round-lbl"></div>')
    for slot in range(1, state.num_teams + 1):
        you = " you" if slot == state.user_slot else ""
        label = f"{slot} · YOU" if slot == state.user_slot else str(slot)
        html.append(f'<div class="team-h{you}">{label}</div>')
    for rnd in range(1, state.num_rounds + 1):
        html.append(f'<div class="round-lbl">{rnd}</div>')
        for slot in range(1, state.num_teams + 1):
            player = state.player_at(slot, rnd)
            on_clock = (
                not state.done
                and rnd == state.current_round
                and slot == state.current_slot
                and player is None
            )
            if player is None:
                cls = "cell on-clock" if on_clock else "cell"
                label = "ON THE CLOCK" if on_clock else ""
                html.append(f'<div class="{cls}">{label}</div>')
                continue
            color = POS_COLORS.get(player.position, "#64748b")
            html.append(
                f'<div class="cell filled" style="background:{color}">'
                f'<div class="nm">{player.name}</div>'
                f'<div class="meta">{player.position} · {player.team}</div>'
                f"</div>"
            )
    html.append("</div>")
    return "".join(html)


def refresh_pool_rows() -> None:
    container = getattr(state, "pool_list", None)
    if container is None:
        return
    container.clear()
    with container:
        render_player_rows()


def render_player_rows() -> None:
    players = state.filtered_pool()[:80]
    if not players:
        ui.label("No players match that search.").classes("muted")
        return
    for p in players:
        selected = " selected" if p.name == state.selected_name else ""
        with ui.row().classes(f"player-row w-full items-center justify-between{selected}"):
            with ui.row().classes("items-center gap-2").on("click", lambda n=p.name: select_row(n)):
                ui.badge(p.position).style(f"background:{POS_COLORS.get(p.position, '#64748b')}")
                with ui.column().classes("gap-0"):
                    ui.label(p.name).classes("font-bold")
                    ui.label(f"{p.team} · bye {p.bye or '—'} · ADP {p.adp:.1f}").classes("muted")
            ui.button("Draft", on_click=lambda n=p.name: draft_named(n)).props(
                "dense unelevated color=amber-8 text-color=black"
            )


def refresh_all() -> None:
    clock_panel.refresh()
    board_panel.refresh()
    refresh_pool_rows()
    advice_panel.refresh()


def draft_named(name: str) -> None:
    if not name:
        ui.notify("Click a player first", type="warning")
        return
    err = state.draft(name)
    if err:
        ui.notify(err, type="warning")
        return
    ui.notify(f"Drafted {name}", type="positive")
    refresh_all()


def undo_pick() -> None:
    err = state.undo()
    if err:
        ui.notify(err, type="warning")
        return
    ui.notify("Pick undone")
    refresh_all()


@ui.refreshable
def clock_panel() -> None:
    cls = "clock-bar yours" if state.is_user_pick and not state.done else "clock-bar"
    with ui.element("div").classes(cls):
        with ui.column().classes("gap-0"):
            ui.label("On the clock").classes("clock-kicker")
            if state.done:
                title = "Draft complete"
            elif state.is_user_pick:
                title = f"Round {state.current_round} · Pick {state.overall} · YOU"
            else:
                title = f"Round {state.current_round} · Pick {state.overall} · Team {state.current_slot}"
            ui.label(title).classes("clock-title")
            ui.label(state.clock_subtitle()).classes("clock-sub")
        with ui.row().classes("items-center"):
            ui.button("Undo pick", on_click=undo_pick).props("outline color=grey-4")
            if not state.done:
                ui.button(
                    "Draft selected",
                    on_click=lambda: draft_named(state.selected_name) if state.selected_name else ui.notify("Click a player first"),
                ).props("unelevated color=amber-8 text-color=black")


@ui.refreshable
def board_panel() -> None:
    with ui.element("div").classes("board-wrap"):
        ui.html(board_markup(), sanitize=False)


def pool_panel() -> None:
    with ui.column().classes("side-card w-full"):
        ui.label("Available players").classes("text-subtitle1 font-bold")
        with ui.row().classes("w-full items-center"):
            search = ui.input(
                placeholder="Search name or team",
                value=state.search,
                on_change=lambda e: (setattr(state, "search", e.value or ""), refresh_pool_rows()),
            ).props("dense outlined dark").classes("flex-grow")
            ui.toggle(
                ["ALL", "QB", "RB", "WR", "TE", "DST", "K"],
                value=state.pos_filter,
                on_change=lambda e: (setattr(state, "pos_filter", e.value or "ALL"), refresh_pool_rows()),
            ).props("dense")

        with ui.scroll_area().classes("w-full").style("height: 52vh"):
            state.pool_list = ui.column().classes("w-full gap-1")
            with state.pool_list:
                render_player_rows()


def select_row(name: str) -> None:
    state.selected_name = name
    refresh_pool_rows()
    ui.notify(f"Selected {name} — hit Draft selected, or Draft on the row")


@ui.refreshable
def advice_panel() -> None:
    with ui.column().classes("side-card w-full"):
        if state.done:
            ui.label("Final rosters").classes("text-subtitle1 font-bold")
            render_roster(state.user_slot, "Your team")
            return

        if state.is_user_pick:
            ui.label("Your pick advice").classes("text-subtitle1 font-bold")
            ui.label("From fantasy_draft_optimizer.py, using your current roster.").classes("muted")
            for note in state.strategy_notes():
                ui.label(f"• {note}").classes("note")
            ui.label("Click a recommendation to draft them").classes("muted q-mt-sm")
            for row in state.recommendation_rows():
                cls = "rec-card best" if row["is_rec"] else "rec-card"
                with ui.element("div").classes(cls).on("click", lambda n=row["name"]: draft_named(n)):
                    with ui.column().classes("gap-0"):
                        tag = "BEST PICK  " if row["is_rec"] else ""
                        ui.label(f"{tag}{row['name']}").classes("font-bold")
                        ui.label(f"{row['pos']} · {row['team']} · ADP {row['adp']} · score {row['score']}").classes("muted")
                    ui.badge(row["pos"]).style(f"background:{POS_COLORS.get(row['pos'], '#64748b')}")
            risk = state.at_risk_names()
            if risk:
                ui.label("Likely gone before you pick again").classes("text-subtitle2 q-mt-md")
                ui.label(" · ".join(risk)).classes("muted")
        else:
            ui.label(f"Assigning Team {state.current_slot}'s pick").classes("text-subtitle1 font-bold")
            ui.label("You pick for everyone. Advice lights up when it is your slot.").classes("muted")
            render_roster(state.current_slot, f"Team {state.current_slot} so far")

        ui.separator()
        render_roster(state.user_slot, "Your roster")


def render_roster(slot: int, title: str) -> None:
    team = state.teams[slot]
    ui.label(title).classes("text-subtitle2 q-mt-sm")
    if not team.roster:
        ui.label("No picks yet").classes("muted")
        return
    for p in team.roster:
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(p.name).classes("font-medium")
            ui.badge(f"{p.position} {p.team}").style(f"background:{POS_COLORS.get(p.position, '#64748b')}")
    counts = "  ".join(f"{pos} {team.pos_count(pos)}" for pos in ("QB", "RB", "WR", "TE", "DST", "K"))
    ui.label(counts).classes("muted")


def start_from_setup(teams: int, slot: int, rounds: int) -> None:
    if not 1 <= slot <= teams:
        ui.notify("Your pick must be within the league size", type="negative")
        return
    ui.notify("Loading player pool…")
    state.start(int(teams), int(slot), int(rounds))
    ui.navigate.to("/room")


@ui.page("/")
def setup_page() -> None:
    ui.dark_mode().enable()
    ui.add_css(CSS)
    with ui.column().classes("absolute-center items-stretch").style("width: min(520px, 92vw)"):
        ui.label("Fantasy Draft Room").classes("text-h4 font-bold")
        ui.label("Sleeper-style board. You click every pick. Optimizer advice appears on your turn.").classes("muted")
        with ui.card().classes("w-full").style("background:#121a2d"):
            teams = ui.slider(min=8, max=14, value=12, step=1).props("label label-always")
            ui.label().bind_text_from(teams, "value", lambda v: f"Teams in the draft: {int(v)}")
            slot = ui.slider(min=1, max=14, value=5, step=1).props("label label-always")
            ui.label().bind_text_from(slot, "value", lambda v: f"Your draft slot: {int(v)}")
            rounds = ui.slider(min=10, max=18, value=15, step=1).props("label label-always")
            ui.label().bind_text_from(rounds, "value", lambda v: f"Rounds: {int(v)}")
            ui.button(
                "Enter draft room",
                on_click=lambda: start_from_setup(teams.value, slot.value, rounds.value),
            ).props("unelevated color=amber-8 text-color=black").classes("w-full q-mt-md")


@ui.page("/room")
def room_page() -> None:
    if not state.started:
        ui.navigate.to("/")
        return
    ui.dark_mode().enable()
    ui.add_css(CSS)
    clock_panel()
    board_panel()
    with ui.grid(columns="1.35fr 0.85fr").classes("w-full q-mt-md gap-3"):
        pool_panel()
        advice_panel()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Fantasy Draft Room", dark=True, reload=False, port=8090, show=True)
