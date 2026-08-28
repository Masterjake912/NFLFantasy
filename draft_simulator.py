#!/usr/bin/env python3
"""Interactive snake-draft simulator. You pick for every team; on your slot,
recommendations come from fantasy_draft_optimizer.py."""
from __future__ import annotations

import argparse
import sys

import fantasy_draft_optimizer as opt

MIN_TEAMS = 12
MAX_TEAMS = 12
DEFAULT_TEAMS = 12
DEFAULT_ROUNDS = 15
BOARD_SIZE = 18
TIP_CANDIDATES = 8


def prompt_int(label: str, default: int, lo: int, hi: int) -> int:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print(f"  Enter a number between {lo} and {hi}.")
            continue
        if lo <= value <= hi:
            return value
        print(f"  Enter a number between {lo} and {hi}.")


def apply_league_settings(num_teams: int, user_slot: int, num_rounds: int) -> None:
    opt.NUM_TEAMS = num_teams
    opt.USER_DRAFT_SLOT = user_slot
    opt.NUM_ROUNDS = num_rounds
    opt.BENCH_SLOTS = num_rounds - sum(opt.ROSTER_STARTERS.values())
    opt.STREAMING_POSITIONS_MIN_ROUND = max(1, num_rounds - 2)


def load_players() -> list:
    players = opt.load_pool()
    opt.load_projections(players, opt.FANTASYPROS_DIR, opt.PROJECTIONS_CSV_PATH)
    opt.load_community_sheet(players, opt.COMMUNITY_SHEET_PATH)
    return players


def overall_to_round_slot(overall: int, num_teams: int) -> tuple[int, int]:
    rnd = (overall - 1) // num_teams + 1
    pos_in_round = (overall - 1) % num_teams
    slot = pos_in_round + 1 if rnd % 2 == 1 else num_teams - pos_in_round
    return rnd, slot


def next_user_overall(overall: int, user_slot: int, num_teams: int, num_rounds: int) -> int | None:
    total = num_teams * num_rounds
    for pick in range(overall + 1, total + 1):
        _, slot = overall_to_round_slot(pick, num_teams)
        if slot == user_slot:
            return pick
    return None


def format_player(p, include_value: bool = True) -> str:
    val_txt = ""
    if include_value:
        if p.vorp is not None:
            val_txt = f"  VORP {p.vorp:>6.1f}"
        else:
            val_txt = f"  val {p.value_score:>5.1f}"
    bye = p.bye if p.bye else "-"
    return f"{p.name:<24} {p.position:<3} {p.team:<4} bye {bye:<3} ADP {p.adp:>6.1f}{val_txt}"


def print_header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_board(available: list, pos: str | None = None, limit: int = BOARD_SIZE) -> None:
    pool = available
    if pos:
        pos = pos.upper()
        pool = [p for p in available if p.position == pos]
        if not pool:
            print(f"  No remaining players at {pos}.")
            return
    print_header(f"AVAILABLE BOARD{' — ' + pos if pos else ''}  (top {min(limit, len(pool))})")
    for i, p in enumerate(pool[:limit], start=1):
        print(f"  {i:>3}. {format_player(p)}")
    leftover = len(pool) - min(limit, len(pool))
    if leftover > 0:
        print(f"  ... {leftover} more. Use  search <name>  or  board QB|RB|WR|TE|DST|K")


def print_roster(team: opt.Team, label: str) -> None:
    print(f"\n  {label}  ({len(team.roster)} players)")
    if not team.roster:
        print("    (empty)")
        return
    for i, p in enumerate(team.roster, start=1):
        print(f"    R{i:<2} {format_player(p, include_value=False)}")
    counts = {pos: team.pos_count(pos) for pos in ("QB", "RB", "WR", "TE", "DST", "K")}
    open_pos = ", ".join(sorted(team.open_starter_positions())) or "starters filled"
    print(f"    Counts: " + "  ".join(f"{k}:{v}" for k, v in counts.items()))
    print(f"    Open starter spots: {open_pos}")


def infer_strategy(team: opt.Team, current_round: int) -> list[str]:
    notes = []
    rb = team.pos_count("RB")
    wr = team.pos_count("WR")
    te = team.pos_count("TE")
    qb = team.pos_count("QB")
    picks_made = len(team.roster)

    if picks_made == 0:
        notes.append("Opening pick: take the best player on the board. Do not force a position.")
        return notes

    last = team.roster[-1]
    notes.append(f"Last pick was {last.name} ({last.position}). Build around that, don't stack the same hole.")

    if picks_made <= 4 and rb == 0:
        notes.append("Zero-RB path: keep hammering WR/TE while RB is cheap later, but don't fall asleep on RB depth.")
    elif picks_made <= 4 and rb == 1 and wr >= 2:
        notes.append("Hero-RB shape: you have one back; prioritize WR until RB2 is a clear value.")
    elif picks_made <= 5 and rb >= 2:
        notes.append("Robust-RB shape: you are set at backfield starters. Shift to WR/TE unless a RB is a smash value.")

    if wr >= 3 and rb < 2:
        notes.append("WR-heavy: next pick should usually be RB unless a WR is a full tier above.")
    if te == 0 and current_round >= 4:
        notes.append("No TE yet: if a top remaining TE is about to cliff, it's fair to spend this pick there.")
    if te >= 1:
        notes.append("TE is covered — don't take a second TE unless he is clearly the best player available.")
    if qb == 0 and current_round >= 6:
        notes.append("Late-QB plan is fine, but don't wait past the last startable QB you actually like.")
    if qb >= 1:
        notes.append("QB is locked. Ignore the position until streaming/bench rounds unless elite value falls.")
    if current_round >= opt.STREAMING_POSITIONS_MIN_ROUND:
        notes.append(f"Streaming window: DST/K are in play from round {opt.STREAMING_POSITIONS_MIN_ROUND} on.")
    else:
        notes.append("Do not take DST or K yet. Those are last-two-round streamers in this model.")

    byes = [p.bye for p in team.roster if p.bye]
    if byes:
        crowded = max(set(byes), key=byes.count)
        if byes.count(crowded) >= 3:
            notes.append(f"Bye-week pile-up on week {crowded}. Prefer a different bye if the values are close.")
    return notes


def likely_gone_before_next(available: list, next_pick: int | None, n: int = 6) -> list:
    if next_pick is None:
        return []
    at_risk = [p for p in available if p.adp <= next_pick]
    return at_risk[:n]


def print_user_tips(
    available: list,
    team: opt.Team,
    current_round: int,
    overall: int,
    user_slot: int,
    num_teams: int,
    num_rounds: int,
) -> None:
    print_header(f"YOUR PICK  —  Round {current_round}, overall {overall}  (slot {user_slot})")
    print_roster(team, "Your roster")

    nxt = next_user_overall(overall, user_slot, num_teams, num_rounds)
    wait = (nxt - overall - 1) if nxt else 0
    if nxt:
        print(f"\n  You pick again at overall {nxt} ({wait} picks in between).")
    else:
        print("\n  This is your last pick of the draft.")

    print("\n  Strategy to lean on right now:")
    for note in infer_strategy(team, current_round):
        print(f"    - {note}")

    rec = opt.recommend_pick(available, team, current_round)
    print(f"\n  Model recommendation: {format_player(rec)}")

    scored = sorted(available, key=lambda p: (-opt.pick_score(p, team, available), p.adp))
    print(f"\n  Top {TIP_CANDIDATES} by the optimizer (need + VORP/value, eligible first):")
    eligible = [p for p in scored if opt.eligible_for_team(p, team, current_round)]
    show = eligible[:TIP_CANDIDATES] if eligible else scored[:TIP_CANDIDATES]
    for i, p in enumerate(show, start=1):
        score = opt.pick_score(p, team, available)
        tag = "  <-- rec" if p is rec else ""
        print(f"    {i:>2}. {format_player(p)}  score {score:>6.1f}{tag}")

    at_risk = likely_gone_before_next(available, nxt)
    if at_risk and wait > 0:
        print("\n  Likely gone before you pick again (ADP at or before that pick):")
        for p in at_risk:
            print(f"    - {format_player(p, include_value=False)}")
        print("  If you want one of these, this is the pick to spend.")


def find_matches(available: list, query: str) -> list:
    q = query.lower().strip()
    if not q:
        return []
    return [p for p in available if q in p.name.lower() or q == p.position.lower()]


def parse_command(raw: str) -> tuple[str, str]:
    raw = raw.strip()
    if not raw:
        return "empty", ""
    parts = raw.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    return cmd, arg


def resolve_pick(available: list, raw: str, board_view: list) -> object | str:
    """Return a Player, or a string command the loop should handle, or None."""
    cmd, arg = parse_command(raw)
    if cmd in ("help", "h", "?"):
        return "help"
    if cmd in ("quit", "exit", "q"):
        return "quit"
    if cmd == "undo":
        return "undo"
    if cmd == "roster":
        return ("roster", arg)
    if cmd == "board":
        return ("board", arg)
    if cmd == "search":
        return ("search", arg)
    if cmd in ("qb", "rb", "wr", "te", "dst", "k") and not arg:
        return ("board", cmd)

    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(board_view):
            return board_view[idx - 1]
        return None

    matches = find_matches(available, raw)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return ("ambiguous", matches)
    return None


def print_help() -> None:
    print("""
  Commands
    <number>          pick that player from the numbered board
    <player name>     pick by name (partial match ok)
    board [POS]       show the available board, optionally QB/RB/WR/TE/DST/K
    search <text>     search remaining players
    roster [slot]     show a roster (omit slot for yours; 'all' for everyone)
    undo              undo the last pick
    help              this list
    quit              abort the draft
""")


def run_draft(num_teams: int, user_slot: int, num_rounds: int) -> None:
    apply_league_settings(num_teams, user_slot, num_rounds)
    players = load_players()
    available = sorted(players, key=lambda p: p.adp)
    teams = {s: opt.Team(s) for s in range(1, num_teams + 1)}
    order = opt.snake_order(num_teams, num_rounds)
    history: list[tuple[int, int, object]] = []
    board_view = available[:BOARD_SIZE]

    print_header(
        f"SNAKE DRAFT  —  {num_teams} teams, {num_rounds} rounds, you are slot {user_slot}"
    )
    print("You pick for every team. Tips appear when it is your slot.")
    print_help()

    pick_index = 0
    while pick_index < len(order):
        rnd, slot = order[pick_index]
        overall = pick_index + 1
        team = teams[slot]
        is_user = slot == user_slot
        on_the_clock = "YOU" if is_user else f"Team {slot}"

        print(f"\n--- Round {rnd}, Pick {overall}  |  {on_the_clock} on the clock ---")
        if is_user:
            print_user_tips(available, team, rnd, overall, user_slot, num_teams, num_rounds)
            board_view = [
                p for p in sorted(available, key=lambda x: (-opt.pick_score(x, team, available), x.adp))
                if opt.eligible_for_team(p, team, rnd)
            ][:BOARD_SIZE]
            if not board_view:
                board_view = available[:BOARD_SIZE]
            print("\n  Numbered board (optimizer ranking):")
            for i, p in enumerate(board_view, start=1):
                print(f"    {i:>2}. {format_player(p)}")
        else:
            board_view = available[:BOARD_SIZE]
            print(f"  Pick for Team {slot}. Numbered board is ADP order.")
            for i, p in enumerate(board_view, start=1):
                print(f"    {i:>2}. {format_player(p)}")

        while True:
            raw = input(f"\n  {on_the_clock} selects (or command): ").strip()
            result = resolve_pick(available, raw, board_view)

            if result is None:
                print("  No match. Use a board number, a name, or type help.")
                continue
            if result == "help":
                print_help()
                continue
            if result == "quit":
                print("  Draft aborted.")
                return
            if result == "undo":
                if not history:
                    print("  Nothing to undo.")
                    continue
                prev_overall, prev_slot, player = history.pop()
                teams[prev_slot].roster.remove(player)
                available.append(player)
                available.sort(key=lambda p: p.adp)
                pick_index = prev_overall - 1
                print(f"  Undid pick {prev_overall}: {player.name} back in the pool.")
                break
            if isinstance(result, tuple):
                kind, payload = result
                if kind == "roster":
                    if payload.lower() == "all" or payload == "":
                        if payload.lower() == "all":
                            for s in range(1, num_teams + 1):
                                tag = "  <-- YOU" if s == user_slot else ""
                                print_roster(teams[s], f"Team {s}{tag}")
                        else:
                            print_roster(teams[user_slot], "Your roster")
                    elif payload.isdigit() and 1 <= int(payload) <= num_teams:
                        s = int(payload)
                        tag = "  <-- YOU" if s == user_slot else ""
                        print_roster(teams[s], f"Team {s}{tag}")
                    else:
                        print(f"  roster [1-{num_teams}|all]")
                    continue
                if kind == "board":
                    pos = payload.upper() if payload else None
                    if pos and pos not in ("QB", "RB", "WR", "TE", "DST", "K"):
                        print("  Positions: QB RB WR TE DST K")
                        continue
                    pool = [p for p in available if not pos or p.position == pos]
                    board_view = pool[:BOARD_SIZE]
                    print_board(available, pos)
                    continue
                if kind == "search":
                    if not payload:
                        print("  search <name>")
                        continue
                    matches = find_matches(available, payload)
                    if not matches:
                        print("  No remaining players matched.")
                        continue
                    board_view = matches[:BOARD_SIZE]
                    print(f"  {len(matches)} match(es):")
                    for i, p in enumerate(board_view, start=1):
                        print(f"    {i:>2}. {format_player(p)}")
                    continue
                if kind == "ambiguous":
                    board_view = payload[:BOARD_SIZE]
                    print("  Multiple matches — pick a number:")
                    for i, p in enumerate(board_view, start=1):
                        print(f"    {i:>2}. {format_player(p)}")
                    continue

            player = result
            if player not in available:
                print("  That player is already drafted.")
                continue
            available.remove(player)
            team.roster.append(player)
            history.append((overall, slot, player))
            print(f"  >> {on_the_clock} drafts {player.name} ({player.position}, {player.team})")
            pick_index += 1
            break

        if result == "undo":
            continue

    print_header("DRAFT COMPLETE")
    for s in range(1, num_teams + 1):
        tag = "  <-- YOU" if s == user_slot else ""
        print_roster(teams[s], f"Team {s}{tag}")
    print("\nYour lineup in draft order:")
    for p in teams[user_slot].roster:
        print(f"  {p.position:<4} {p.name:<24} {p.team:<4} ADP {p.adp:.1f}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive fantasy draft simulator")
    parser.add_argument("--teams", type=int, default=None, help=f"{MIN_TEAMS}-{MAX_TEAMS} (default {DEFAULT_TEAMS})")
    parser.add_argument("--slot", type=int, default=None, help="Your draft position, 1-indexed")
    parser.add_argument("--rounds", type=int, default=None, help=f"Rounds (default {DEFAULT_ROUNDS})")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    print_header("FANTASY DRAFT SIMULATOR")
    print("Keep fantasy_draft_optimizer.py as-is. This session uses it for live pick advice.")

    num_teams = args.teams
    if num_teams is None:
        num_teams = prompt_int("How many people in the draft?", DEFAULT_TEAMS, MIN_TEAMS, MAX_TEAMS)
    elif not MIN_TEAMS <= num_teams <= MAX_TEAMS:
        raise SystemExit(f"--teams must be {MIN_TEAMS}-{MAX_TEAMS}")

    user_slot = args.slot
    if user_slot is None:
        user_slot = prompt_int("What pick are you? (1 = first overall)", 1, 1, num_teams)
    elif not 1 <= user_slot <= num_teams:
        raise SystemExit(f"--slot must be 1-{num_teams}")

    num_rounds = args.rounds
    if num_rounds is None:
        num_rounds = prompt_int("How many rounds?", DEFAULT_ROUNDS, 8, 20)
    elif not 8 <= num_rounds <= 20:
        raise SystemExit("--rounds must be 8-20")

    run_draft(num_teams, user_slot, num_rounds)


if __name__ == "__main__":
    main()
