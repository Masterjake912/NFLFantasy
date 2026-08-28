#!/usr/bin/env python3
import csv
import io
import math
import os
from dataclasses import dataclass, field
from typing import Optional

NUM_TEAMS = 12
USER_DRAFT_SLOT = 5
NUM_ROUNDS = 15

ROSTER_STARTERS = {
    "QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1,
}
FLEX_ELIGIBLE = {"RB", "WR", "TE"}
BENCH_SLOTS = NUM_ROUNDS - sum(ROSTER_STARTERS.values())

MAX_ROSTER_BY_POS = {"QB": 3, "RB": 7, "WR": 7, "TE": 3, "DST": 1, "K": 1}
STREAMING_POSITIONS_MIN_ROUND = max(1, NUM_ROUNDS - 2)
RISK_TIEBREAK_WEIGHT = 0.15
ADP_CSV_PATH = "adp_2026_ppr.csv"
FANTASYPROS_DIR = "FantasyPros"
PROJECTIONS_CSV_PATH = None
COMMUNITY_SHEET_PATH = "community_sheet_2026.csv"

_ADP_CSV = """Name,Position,Team,Bye,ADP,ADP_StdDev
Jahmyr Gibbs,RB,DET,6,1.5,0.7
Bijan Robinson,RB,ATL,11,2.2,0.6
Puka Nacua,WR,LAR,11,3.1,0.8
Ja'Marr Chase,WR,CIN,6,3.8,1.0
Jaxon Smith-Njigba,WR,SEA,11,5.5,1.1
Amon-Ra St. Brown,WR,DET,6,6.4,1.3
Christian McCaffrey,RB,SF,8,6.6,1.6
Jonathan Taylor,RB,IND,13,7.5,1.7
Drake London,WR,ATL,11,10.2,1.8
De'Von Achane,RB,MIA,6,10.6,1.9
CeeDee Lamb,WR,DAL,14,10.7,1.9
Justin Jefferson,WR,MIN,6,11.7,2.3
James Cook III,RB,BUF,7,12.6,2.8
Chase Brown,RB,CIN,6,13.4,2.5
Rashee Rice,WR,KC,5,14.9,2.3
Derrick Henry,RB,BAL,13,17.4,2.7
A.J. Brown,WR,NE,11,17.6,3.2
Ashton Jeanty,RB,LV,13,17.6,5.6
Saquon Barkley,RB,PHI,10,19.3,3.4
Chris Olave,WR,NO,8,19.8,3.3
Nico Collins,WR,HOU,8,20.4,2.8
George Pickens,WR,DAL,14,20.7,3.1
Kenneth Walker,RB,KC,5,21.6,4.2
Omarion Hampton,RB,LAC,7,23.3,4.4
Garrett Wilson,WR,NYJ,13,25.6,3.1
Zay Flowers,WR,BAL,13,25.9,3.2
Malik Nabers,WR,NYG,8,26.8,3.5
Jeremiyah Love,RB,ARI,14,27.8,3.8
Trey McBride,TE,ARI,14,28.9,4.6
DeVonta Smith,WR,PHI,10,29.5,3.5
Josh Jacobs,RB,GB,11,31.1,3.5
Tetairoa McMillan,WR,CAR,5,31.5,3.8
Kyren Williams,RB,LAR,11,32.0,4.3
Josh Allen,QB,BUF,7,33.7,9.1
Breece Hall,RB,NYJ,13,34.7,4.2
Emeka Egbuka,WR,TB,10,34.8,4.0
Brock Bowers,TE,LV,13,35.0,7.1
Tee Higgins,WR,CIN,6,36.6,5.0
Javonte Williams,RB,DAL,14,37.0,4.6
Ladd McConkey,WR,LAC,7,37.7,4.5
Travis Etienne Jr.,RB,NO,8,38.7,5.1
Cam Skattebo,RB,NYG,8,38.8,5.4
Davante Adams,WR,LAR,11,42.0,4.5
Jameson Williams,WR,DET,6,44.5,4.7
Bucky Irving,RB,TB,10,45.2,4.9
Jaylen Waddle,WR,DEN,10,45.2,5.4
D'Andre Swift,RB,CHI,10,45.8,4.5
Terry McLaurin,WR,WAS,7,47.4,4.9
DJ Moore,WR,BUF,7,47.8,6.2
Quinshon Judkins,RB,CLE,11,50.8,5.2
Drake Maye,QB,NE,11,51.2,7.8
Bhayshul Tuten,RB,JAX,7,52.9,5.5
Rome Odunze,WR,CHI,10,53.9,5.8
Mike Evans,WR,SF,8,54.5,6.4
Luther Burden III,WR,CHI,10,56.2,7.2
Colston Loveland,TE,CHI,10,56.5,9.0
Lamar Jackson,QB,BAL,13,56.6,7.1
Joe Burrow,QB,CIN,6,57.2,7.7
David Montgomery,RB,HOU,8,58.2,6.2
Christian Watson,WR,GB,11,58.9,6.5
Jaylen Warren,RB,PIT,9,59.0,5.9
Courtland Sutton,WR,DEN,10,60.2,6.5
TreVeyon Henderson,RB,NE,11,63.0,6.5
Parker Washington,WR,JAX,7,64.1,7.5
DK Metcalf,WR,PIT,9,64.4,6.9
Rhamondre Stevenson,RB,NE,11,64.9,6.8
Dak Prescott,QB,DAL,14,65.1,8.4
Tyler Warren,TE,IND,13,65.2,8.9
Marvin Harrison Jr.,WR,ARI,14,65.3,7.5
Alec Pierce,WR,IND,13,68.7,7.4
Tony Pollard,RB,TEN,9,70.3,6.6
Jayden Daniels,QB,WAS,7,71.9,11.0
Brian Thomas Jr.,WR,JAX,7,72.7,7.4
Michael Pittman Jr.,WR,PIT,9,74.7,7.8
Rico Dowdle,RB,PIT,9,75.2,7.5
Jadarian Price,RB,SEA,11,75.2,10.3
Kyle Pitts Sr.,TE,ATL,11,75.3,9.7
Michael Wilson,WR,ARI,14,76.3,8.0
Matthew Stafford,QB,LAR,11,77.1,11.1
Harold Fannin Jr.,TE,CLE,11,77.5,7.5
Carnell Tate,WR,TEN,9,78.4,9.1
Jalen Hurts,QB,PHI,10,78.4,10.8
Chris Godwin Jr.,WR,TB,10,79.3,8.2
Chuba Hubbard,RB,CAR,5,81.2,10.3
Seattle Defense,DST,SEA,11,81.7,8.7
Jakobi Meyers,WR,JAX,7,86.5,7.7
Wan'Dale Robinson,WR,TEN,9,86.7,8.4
Denver Defense,DST,DEN,10,86.8,7.1
Brock Purdy,QB,SF,8,87.2,11.6
Josh Downs,WR,IND,13,87.7,8.4
J.K. Dobbins,RB,DEN,10,87.7,10.6
Caleb Williams,QB,CHI,10,90.2,12.0
Trevor Lawrence,QB,JAX,7,91.4,12.4
Stefon Diggs,WR,WAS,7,91.5,9.2
RJ Harvey,RB,DEN,10,92.3,12.8
Kenny Gainwell,RB,TB,10,92.3,10.7
Jayden Reed,WR,GB,11,93.8,8.2
Jonathon Brooks,RB,CAR,5,94.6,13.3
Quentin Johnston,WR,LAC,7,97.4,8.9
Jordan Addison,WR,MIN,6,97.4,8.5
Houston Defense,DST,HOU,8,97.8,9.5
Tucker Kraft,TE,GB,11,98.1,18.9
Jared Goff,QB,DET,6,100.6,13.2
Patrick Mahomes,QB,KC,5,102.2,12.7
Khalil Shakir,WR,BUF,7,102.4,8.7
Travis Kelce,TE,KC,5,104.0,20.9
Aaron Jones Sr.,RB,MIN,6,104.3,12.4
Justin Herbert,QB,LAC,7,105.2,14.1
Xavier Worthy,WR,KC,5,105.3,8.4
Dallas Goedert,TE,PHI,10,105.9,21.4
Matthew Golden,WR,GB,11,106.6,8.9
Deebo Samuel Sr.,WR,SF,8,107.3,10.0
LA Rams Defense,DST,LAR,11,107.7,11.4
George Kittle,TE,SF,8,109.8,21.3
Minnesota Defense,DST,MIN,6,110.4,10.1
Kyle Monangai,RB,CHI,10,110.8,12.9
Bo Nix,QB,DEN,10,111.5,13.1
Romeo Doubs,WR,NE,11,113.2,9.4
San Francisco Defense,DST,SF,8,113.5,40.0
Rachaad White,RB,WAS,7,113.5,13.6
Sam LaPorta,TE,DET,6,113.8,22.0
Jacory Croskey-Merritt,RB,WAS,7,115.2,14.2
Makai Lemon,WR,PHI,10,115.9,10.8
Jordan Mason,RB,MIN,6,116.6,16.1
Jaxson Dart,QB,NYG,8,116.9,12.1
KC Concepcion,WR,CLE,11,121.0,10.6
Jalen Coker,WR,CAR,5,121.6,10.4
Blake Corum,RB,LAR,11,122.5,16.3
Jerry Jeudy,WR,CLE,11,127.1,11.5
Mark Andrews,TE,BAL,13,128.4,17.8
New England Defense,DST,NE,11,128.5,15.7
Rashid Shaheed,WR,SEA,11,128.5,11.1
Brandon Aubrey,K,DAL,14,128.5,21.9
Detroit Defense,DST,DET,6,129.2,14.5
Baker Mayfield,QB,TB,10,129.9,10.6
Jake Ferguson,TE,DAL,14,131.0,16.9
Tyjae Spears,RB,TEN,9,131.3,11.2
Tre Tucker,WR,LV,13,132.0,8.9
Keenan Allen,WR,IND,13,132.1,11.9
Jayden Higgins,WR,HOU,8,132.5,8.7
De'Zhaun Stribling,WR,SF,8,132.8,16.8
Kyler Murray,QB,MIN,6,134.0,11.1
Zach Charbonnet,RB,SEA,11,134.2,16.2
Pittsburgh Defense,DST,PIT,9,134.4,15.2
Jalen McMillan,WR,TB,10,134.8,12.2
Tyler Shough,QB,NO,8,135.1,11.9
Isaiah Likely,TE,NYG,8,136.3,18.2
Jason Myers,K,SEA,11,136.8,18.2
Ka'imi Fairbairn,K,HOU,8,137.0,20.0
Philadelphia Defense,DST,PHI,10,137.9,16.5
Denzel Boston,WR,CLE,11,138.0,15.0
LA Chargers Defense,DST,LAC,7,140.1,14.7
Woody Marks,RB,HOU,8,140.2,16.1
Cameron Dicker,K,LAC,7,141.9,19.3
Sam Darnold,QB,SEA,11,143.4,13.1
Chimere Dike,WR,TEN,9,144.3,28.6
Calvin Ridley,WR,TEN,9,144.8,11.8
Mike Washington Jr.,RB,LV,13,145.8,27.2
Juwan Johnson,TE,NO,8,147.0,19.1
Jordan Love,QB,GB,11,147.0,13.4
Jauan Jennings,WR,MIN,6,147.0,11.9
Jake Bates,K,DET,6,147.3,18.5
Dalton Kincaid,TE,BUF,7,147.4,21.2
Harrison Mevis,K,LAR,11,147.5,16.3
Malik Washington,WR,MIA,6,148.7,13.4
Cyrus Allen,WR,KC,5,148.8,22.6
Jonah Coleman,RB,DEN,10,149.5,19.3
Alvin Kamara,RB,NO,8,150.3,17.1
Cam Little,K,JAX,7,151.7,17.5
Cooper Kupp,WR,SEA,11,151.8,19.3
Isiah Pacheco,RB,DET,6,152.4,20.3
Jalen Nailor,WR,LV,13,152.9,16.3
Joey Slye,K,TEN,9,153.2,11.5
Chase McLaughlin,K,TB,10,153.7,18.3
David Njoku,TE,LAC,7,154.0,20.3
Rashod Bateman,WR,BAL,13,154.4,14.9
Tyler Allgeier,RB,ARI,14,154.9,21.0
MarShawn Lloyd,RB,GB,11,154.9,20.6
Hunter Henry,TE,NE,11,155.0,23.0
Tyler Loop,K,BAL,13,155.8,15.5
Jacksonville Defense,DST,JAX,7,155.8,14.5
Jordyn Tyson,WR,NO,8,156.1,15.9
Green Bay Defense,DST,GB,11,156.2,14.6
Pat Bryant,WR,DEN,10,156.9,28.8
Tank Dell,WR,HOU,8,156.9,15.2
Ja'Kobi Lane,WR,BAL,13,157.0,18.1
Keaton Mitchell,RB,LAC,7,157.1,21.1
Chris Rodriguez Jr.,RB,JAX,7,157.2,18.4
Dylan Sampson,RB,CLE,11,157.6,14.4
Kaelon Black,RB,SF,8,157.9,25.0
Kenyon Sadiq,TE,NYJ,13,158.0,17.7
Tyrone Tracy Jr.,RB,NYG,8,158.0,15.5
Braelon Allen,RB,NYJ,13,158.1,21.4
Emmett Johnson,RB,KC,5,158.1,12.6
Tyler Bass,K,BUF,7,158.2,24.6
C.J. Stroud,QB,HOU,8,158.2,14.0
Cleveland Defense,DST,CLE,11,158.7,14.9
Najee Harris,RB,NYG,8,158.8,22.4
AJ Barner,TE,SEA,11,158.9,26.5
Chris Boswell,K,PIT,9,158.9,20.5
"""


@dataclass
class Player:
    name: str
    position: str
    team: str
    bye: int
    adp: float
    adp_stdev: float
    proj_points: Optional[float] = None
    vorp: Optional[float] = None
    community_tier: Optional[int] = None
    community_pts: Optional[float] = None
    community_value: Optional[float] = None
    community_ecr: Optional[str] = None

    @property
    def value_score(self) -> float:
        return round(100 * math.exp(-self.adp / 60), 1)


def load_pool(csv_path: str = ADP_CSV_PATH) -> list:
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        source = f"refreshed file: {csv_path}"
    else:
        reader = csv.DictReader(io.StringIO(_ADP_CSV))
        rows = list(reader)
        source = "embedded snapshot (2026-08-27)"

    players = []
    for row in rows:
        players.append(
            Player(
                name=row["Name"].strip(),
                position=row["Position"].strip().upper(),
                team=row["Team"].strip(),
                bye=int(row["Bye"]) if row.get("Bye") else 0,
                adp=float(row["ADP"]),
                adp_stdev=float(row.get("ADP_StdDev", 0) or 0),
            )
        )
    players.sort(key=lambda p: p.adp)
    print(f"Loaded {len(players)} players from {source}.")
    return players


_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_name(name: str) -> str:
    cleaned = name.replace(".", "").replace("'", "").strip()
    parts = cleaned.split()
    while parts and parts[-1].lower() in _NAME_SUFFIXES:
        parts.pop()
    return " ".join(parts).lower()


_DST_FULL_NAME_TO_LABEL = {
    "Arizona Cardinals": "Arizona Defense", "Atlanta Falcons": "Atlanta Defense",
    "Baltimore Ravens": "Baltimore Defense", "Buffalo Bills": "Buffalo Defense",
    "Carolina Panthers": "Carolina Defense", "Chicago Bears": "Chicago Defense",
    "Cincinnati Bengals": "Cincinnati Defense", "Cleveland Browns": "Cleveland Defense",
    "Dallas Cowboys": "Dallas Defense", "Denver Broncos": "Denver Defense",
    "Detroit Lions": "Detroit Defense", "Green Bay Packers": "Green Bay Defense",
    "Houston Texans": "Houston Defense", "Indianapolis Colts": "Indianapolis Defense",
    "Jacksonville Jaguars": "Jacksonville Defense", "Kansas City Chiefs": "Kansas City Defense",
    "Las Vegas Raiders": "Las Vegas Defense", "Los Angeles Chargers": "LA Chargers Defense",
    "Los Angeles Rams": "LA Rams Defense", "Miami Dolphins": "Miami Defense",
    "Minnesota Vikings": "Minnesota Defense", "New England Patriots": "New England Defense",
    "New Orleans Saints": "New Orleans Defense", "New York Giants": "NY Giants Defense",
    "New York Jets": "NY Jets Defense", "Philadelphia Eagles": "Philadelphia Defense",
    "Pittsburgh Steelers": "Pittsburgh Defense", "San Francisco 49ers": "San Francisco Defense",
    "Seattle Seahawks": "Seattle Defense", "Tampa Bay Buccaneers": "Tampa Bay Defense",
    "Tennessee Titans": "Tennessee Defense", "Washington Commanders": "Washington Defense",
}

_FANTASYPROS_FILES = {
    "QB": "FantasyPros_Fantasy_Football_Projections_QB.csv",
    "RB": "FantasyPros_Fantasy_Football_Projections_RB.csv",
    "WR": "FantasyPros_Fantasy_Football_Projections_WR.csv",
    "TE": "FantasyPros_Fantasy_Football_Projections_TE.csv",
    "K": "FantasyPros_Fantasy_Football_Projections_K.csv",
    "DST": "FantasyPros_Fantasy_Football_Projections_DST.csv",
}


def _load_fantasypros_dir(dir_path: str) -> dict:
    proj = {}
    loaded_files = 0
    for pos, filename in _FANTASYPROS_FILES.items():
        path = os.path.join(dir_path, filename)
        if not os.path.exists(path):
            print(f"  (no {filename} in {dir_path}/ — skipping {pos} projections)")
            continue
        with open(path, newline="", encoding="utf-8") as f:
            rows_here = 0
            for row in csv.DictReader(f):
                name = (row.get("Player") or "").strip()
                fpts_raw = (row.get("FPTS") or "").strip()
                if not name or not fpts_raw:
                    continue
                try:
                    fpts = float(fpts_raw)
                except ValueError:
                    continue
                if pos == "DST":
                    name = _DST_FULL_NAME_TO_LABEL.get(name, f"{name} Defense")
                proj[normalize_name(name)] = fpts
                rows_here += 1
        loaded_files += 1
        print(f"  loaded {rows_here} {pos} rows from {filename}")
    print(f"Loaded FantasyPros projections from {loaded_files}/{len(_FANTASYPROS_FILES)} "
          f"expected files in {dir_path}/.")
    return proj


def load_projections(players, fantasypros_dir=None, flat_csv_path=None) -> bool:
    proj_by_key = {}
    source_desc = None
    if fantasypros_dir and os.path.isdir(fantasypros_dir):
        proj_by_key = _load_fantasypros_dir(fantasypros_dir)
        source_desc = f"FantasyPros exports in {fantasypros_dir}/"
    elif flat_csv_path and os.path.exists(flat_csv_path):
        with open(flat_csv_path, newline="", encoding="utf-8") as f:
            proj_by_key = {
                normalize_name(r["Name"].strip()): float(r["Proj_Points"])
                for r in csv.DictReader(f)
            }
        source_desc = f"flat projections file: {flat_csv_path}"
    if not proj_by_key:
        return False
    matched = 0
    for p in players:
        key = normalize_name(p.name)
        if key in proj_by_key:
            p.proj_points = proj_by_key[key]
            matched += 1
    print(f"Matched {matched}/{len(players)} ADP-pool players to projections from {source_desc}.")
    compute_vorp(players)
    return True


def load_community_sheet(players, csv_path) -> bool:
    if not csv_path or not os.path.exists(csv_path):
        return False
    rows_by_key = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = (r.get("Name") or "").strip()
            if not name:
                continue
            rows_by_key[normalize_name(name)] = r
    matched = 0
    for p in players:
        r = rows_by_key.get(normalize_name(p.name))
        if not r:
            continue
        try:
            p.community_tier = int(r["Tier"]) if r.get("Tier") else None
            p.community_pts = float(r["PTS"]) if r.get("PTS") else None
            p.community_value = float(r["VALUE"]) if r.get("VALUE") else None
        except ValueError:
            pass
        p.community_ecr = r.get("ECR") or None
        matched += 1
    print(f"Matched {matched}/{len(players)} ADP-pool players to the community sheet: {csv_path}.")
    return matched > 0


def compute_vorp(players) -> None:
    projected = [p for p in players if p.proj_points is not None]
    if not projected:
        return
    by_pos = {}
    for p in projected:
        by_pos.setdefault(p.position, []).append(p)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda p: -p.proj_points)
    locked_counts = {
        "QB": ROSTER_STARTERS["QB"] * NUM_TEAMS, "RB": ROSTER_STARTERS["RB"] * NUM_TEAMS,
        "WR": ROSTER_STARTERS["WR"] * NUM_TEAMS, "TE": ROSTER_STARTERS["TE"] * NUM_TEAMS,
        "DST": ROSTER_STARTERS["DST"] * NUM_TEAMS, "K": ROSTER_STARTERS["K"] * NUM_TEAMS,
    }
    starter_counts = dict(locked_counts)
    flex_pool = []
    for pos in FLEX_ELIGIBLE:
        leftover = by_pos.get(pos, [])[locked_counts.get(pos, 0):]
        flex_pool.extend(leftover)
    flex_pool.sort(key=lambda p: -p.proj_points)
    flex_slots_total = ROSTER_STARTERS["FLEX"] * NUM_TEAMS
    for p in flex_pool[:flex_slots_total]:
        starter_counts[p.position] += 1
    replacement_level = {}
    for pos, plist in by_pos.items():
        idx = starter_counts.get(pos, 0)
        if idx < len(plist):
            replacement_level[pos] = plist[idx].proj_points
        elif plist:
            replacement_level[pos] = plist[-1].proj_points
        else:
            replacement_level[pos] = 0.0
    for p in projected:
        p.vorp = round(p.proj_points - replacement_level.get(p.position, 0.0), 1)


def assign_tiers(ranked_players, key=lambda p: p.adp) -> dict:
    tiers = {}
    tier = 1
    for i, p in enumerate(ranked_players):
        tiers[p.name] = tier
        if i + 1 < len(ranked_players):
            gap = key(ranked_players[i + 1]) - key(ranked_players[i])
            threshold = max(4.0, key(ranked_players[i]) * 0.12)
            if gap >= threshold:
                tier += 1
    return tiers


def snake_order(num_teams, num_rounds):
    order = []
    for rnd in range(1, num_rounds + 1):
        picks = range(1, num_teams + 1) if rnd % 2 == 1 else range(num_teams, 0, -1)
        for slot in picks:
            order.append((rnd, slot))
    return order


class Team:
    def __init__(self, slot):
        self.slot = slot
        self.roster = []

    def pos_count(self, pos):
        return sum(1 for p in self.roster if p.position == pos)

    def starters_filled(self):
        filled = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "FLEX": 0, "DST": 0, "K": 0}
        flex_overflow = []
        for p in self.roster:
            if p.position in ("QB", "DST", "K"):
                filled[p.position] += 1
            elif p.position in FLEX_ELIGIBLE:
                if filled[p.position] < ROSTER_STARTERS[p.position]:
                    filled[p.position] += 1
                else:
                    flex_overflow.append(p)
        filled["FLEX"] = min(len(flex_overflow), ROSTER_STARTERS["FLEX"])
        return filled

    def open_starter_positions(self):
        filled = self.starters_filled()
        open_pos = set()
        for pos in ("QB", "DST", "K"):
            if filled[pos] < ROSTER_STARTERS[pos]:
                open_pos.add(pos)
        flex_open = filled["FLEX"] < ROSTER_STARTERS["FLEX"]
        for pos in ("RB", "WR", "TE"):
            if filled[pos] < ROSTER_STARTERS[pos] or flex_open:
                open_pos.add(pos)
        return open_pos

    def roster_full(self):
        return len(self.roster) >= NUM_ROUNDS


def eligible_for_team(player, team, current_round):
    if team.pos_count(player.position) >= MAX_ROSTER_BY_POS.get(player.position, 99):
        return False
    if player.position in ("DST", "K") and current_round < STREAMING_POSITIONS_MIN_ROUND:
        return False
    return True


# How much of the "cliff" (gap to the next-best player at this position)
# gets converted into a need bonus. 0.5 means: if waiting one more pick would
# cost you half the cliff's value, that shows up in the score. Capped so a
# single freak outlier player can't dominate every decision.
SCARCITY_BONUS_WEIGHT = 0.5
SCARCITY_BONUS_CAP = 8.0

# Once a team already has this many players at a position that only starts 1
# (QB, TE, DST, K), stop giving it any need bonus at all — there's no more
# "need," just optional bench value, and BPA should take over.
SATURATION_AFTER = {"QB": 1, "TE": 1, "DST": 1, "K": 1}


def pick_score(player, team, available):
    """Ranking key for 'best pick right now'. Need is scaled by the real
    positional cliff (this player's value vs. the next-best remaining player at
    the same position) instead of a flat bonus — so a position only gets
    pushed early when waiting would actually cost you something, not just
    because the slot happens to be unfilled."""
    base = player.vorp if player.vorp is not None else player.value_score
    pos = player.position

    need_bonus = 0.0
    if pos in team.open_starter_positions():
        already_has = team.pos_count(pos)
        cap = SATURATION_AFTER.get(pos)
        if cap is None or already_has < cap:
            same_pos_left = [p for p in available if p.position == pos and p is not player]
            if same_pos_left:
                next_best = max(
                    same_pos_left,
                    key=lambda p: p.vorp if p.vorp is not None else p.value_score,
                )
                next_val = next_best.vorp if next_best.vorp is not None else next_best.value_score
                cliff = max(0.0, base - next_val)
                need_bonus = min(SCARCITY_BONUS_CAP, cliff * SCARCITY_BONUS_WEIGHT)
            else:
                need_bonus = SCARCITY_BONUS_CAP  # last one left at the position

    risk_nudge = RISK_TIEBREAK_WEIGHT * (player.adp_stdev or 0) * 0.1
    return base + need_bonus - risk_nudge


def recommend_pick(available, team, current_round):
    candidates = [p for p in available if eligible_for_team(p, team, current_round)]
    if not candidates:
        candidates = available
    candidates.sort(key=lambda p: (-pick_score(p, team, available), p.adp))
    return candidates[0]


def simulate_draft(players, num_teams=NUM_TEAMS, num_rounds=NUM_ROUNDS, user_slot=USER_DRAFT_SLOT):
    order = snake_order(num_teams, num_rounds)
    teams = {s: Team(s) for s in range(1, num_teams + 1)}
    available = sorted(players, key=lambda p: p.adp)
    log = []
    for overall_pick, (rnd, slot) in enumerate(order, start=1):
        team = teams[slot]
        pick = recommend_pick(available, team, rnd)
        available.remove(pick)
        team.roster.append(pick)
        log.append({"overall": overall_pick, "round": rnd, "slot": slot,
                     "is_user": slot == user_slot, "player": pick})
    return log, teams


def print_master_board(players, top_n=60):
    tiers = assign_tiers(sorted(players, key=lambda p: p.adp), key=lambda p: p.adp)
    print("\n" + "=" * 78)
    print(f"MASTER BOARD — Top {top_n} overall (all positions)")
    print("=" * 78)
    header = f"{'#':<4}{'Player':<26}{'Pos':<5}{'Team':<6}{'Bye':<5}{'ADP':<8}{'Tier':<6}"
    header += f"{'VORP':<8}" if any(p.vorp is not None for p in players) else f"{'Value':<8}"
    print(header)
    for i, p in enumerate(sorted(players, key=lambda p: p.adp)[:top_n], start=1):
        val = p.vorp if p.vorp is not None else p.value_score
        print(f"{i:<4}{p.name:<26}{p.position:<5}{p.team:<6}{p.bye:<5}{p.adp:<8.1f}"
              f"T{tiers[p.name]:<5}{val:<8.1f}")


def print_positional_boards(players, positions=("QB", "RB", "WR", "TE", "DST", "K"), top_n=15):
    for pos in positions:
        pos_players = sorted([p for p in players if p.position == pos], key=lambda p: p.adp)
        tiers = assign_tiers(pos_players, key=lambda p: p.adp)
        print(f"\n--- {pos} (top {min(top_n, len(pos_players))}) ---")
        for i, p in enumerate(pos_players[:top_n], start=1):
            val = p.vorp if p.vorp is not None else p.value_score
            print(f"  {i:>2}. {p.name:<24} ADP {p.adp:>6.1f}  Tier {tiers[p.name]}  "
                  f"(std {p.adp_stdev:>4.1f})  val {val:>6.1f}")


def print_value_flags(players, top_n=15):
    projected = [p for p in players if p.vorp is not None]
    if not projected:
        return
    by_adp = sorted(projected, key=lambda p: p.adp)
    by_vorp = sorted(projected, key=lambda p: -p.vorp)
    adp_rank = {p.name: i for i, p in enumerate(by_adp, start=1)}
    vorp_rank = {p.name: i for i, p in enumerate(by_vorp, start=1)}
    deltas = [(adp_rank[p.name] - vorp_rank[p.name], p) for p in projected]
    deltas.sort(key=lambda t: -t[0])
    print("\n" + "=" * 78)
    print("VALUE FLAGS (VORP rank vs. ADP rank)")
    print("=" * 78)
    print("Potential values (my rank well ahead of the market):")
    for delta, p in deltas[:top_n]:
        if delta > 0:
            print(f"  {p.name:<24} ADP #{adp_rank[p.name]:<4} -> Value #{vorp_rank[p.name]:<4} (+{delta})")
    print("Potential reaches (market ahead of my rank):")
    for delta, p in reversed(deltas[-top_n:]):
        if delta < 0:
            print(f"  {p.name:<24} ADP #{adp_rank[p.name]:<4} -> Value #{vorp_rank[p.name]:<4} ({delta})")


def print_community_comparison(players, top_n=40):
    has_community = [p for p in players if p.community_pts is not None]
    if not has_community:
        return
    print("\n" + "=" * 96)
    print("COMMUNITY SHEET vs. YOUR BOARD")
    print("=" * 96)
    header = (f"{'Player':<24}{'Pos':<5}{'ADP':<8}{'My VORP':<10}"
              f"{'Comm.Tier':<11}{'Comm.PTS':<10}{'Comm.VALUE':<12}{'Comm.ECR':<9}")
    print(header)
    ranked = sorted(has_community, key=lambda p: p.adp)[:top_n]
    for p in ranked:
        my_val = f"{p.vorp:.1f}" if p.vorp is not None else "-"
        print(f"{p.name:<24}{p.position:<5}{p.adp:<8.1f}{my_val:<10}"
              f"{p.community_tier if p.community_tier is not None else '-':<11}"
              f"{p.community_pts if p.community_pts is not None else '-':<10}"
              f"{p.community_value if p.community_value is not None else '-':<12}"
              f"{p.community_ecr or '-':<9}")


def print_draft_strategy(players, num_teams=NUM_TEAMS):
    """Turns the VORP cliffs into plain-English 'target this round' guidance per
    position, instead of making you eyeball the tier tables. A pick's 'round'
    here is estimated as (rank at that position among startable-relevant depth)
    translated via ADP into a round number for a num_teams-team draft — i.e.
    'if you wait past here, the drop-off is real.'"""
    projected = [p for p in players if p.vorp is not None]
    if not projected:
        print("\n(No projections loaded — skipping strategy report.)")
        return

    print("\n" + "=" * 78)
    print("DRAFT STRATEGY — where the real cliffs are, by position")
    print("=" * 78)
    for pos in ("QB", "TE", "DST", "K", "RB", "WR"):
        plist = sorted([p for p in projected if p.position == pos], key=lambda p: -p.vorp)
        if len(plist) < 2:
            continue
        # Find the single biggest VORP drop in the first ~40 ranked players at
        # this position — that's "the cliff."
        window = plist[:40]
        biggest_drop = 0.0
        cliff_idx = 0
        for i in range(len(window) - 1):
            drop = window[i].vorp - window[i + 1].vorp
            if drop > biggest_drop:
                biggest_drop = drop
                cliff_idx = i
        cliff_player = window[cliff_idx]
        after_cliff = window[cliff_idx + 1] if cliff_idx + 1 < len(window) else None
        cliff_round = max(1, round(cliff_player.adp / num_teams + 0.49))
        print(f"\n{pos}:")
        print(f"  Last player before the big drop: {cliff_player.name} "
              f"(VORP {cliff_player.vorp}, ADP {cliff_player.adp:.1f} -> ~Round {cliff_round})")
        if after_cliff:
            print(f"  Next player after the drop:     {after_cliff.name} "
                  f"(VORP {after_cliff.vorp}, ADP {after_cliff.adp:.1f})  "
                  f"[drop of {biggest_drop:.1f} VORP]")
        if pos in ("DST", "K"):
            print(f"  -> Flat position, drop is small in absolute terms — confirms streaming "
                  f"late (round {STREAMING_POSITIONS_MIN_ROUND}+) is correct, don't reach.")
        elif biggest_drop > 15:
            print(f"  -> Real cliff. If you want a player from this tier, get them by "
                  f"~Round {cliff_round} or plan to punt the position until it's flat again.")
        else:
            print(f"  -> Gradual decline, no sharp cliff — fine to wait and take best "
                  f"available elsewhere.")


def print_user_draft_plan(log):
    print("\n" + "=" * 78)
    print(f"YOUR SIMULATED DRAFT — slot {USER_DRAFT_SLOT} of {NUM_TEAMS}, {NUM_ROUNDS} rounds")
    print("=" * 78)
    for entry in log:
        if entry["is_user"]:
            p = entry["player"]
            print(f"Round {entry['round']:>2}, Pick {entry['overall']:>3}: "
                  f"{p.name} ({p.position}, {p.team}) — ADP {p.adp:.1f}")


def print_all_slots_draft_plan(log, num_teams=NUM_TEAMS):
    """Same simulation, shown for every draft slot (1-num_teams), not just yours.
    Useful for seeing how the recommend_pick logic behaves from each spot in the
    order — early-slot vs. late-slot vs. turn strategy all look different."""
    print("\n" + "=" * 78)
    print(f"SIMULATED DRAFT — ALL {num_teams} SLOTS, {NUM_ROUNDS} rounds")
    print("=" * 78)
    picks_by_slot = {s: [] for s in range(1, num_teams + 1)}
    for entry in log:
        picks_by_slot[entry["slot"]].append(entry)

    for slot in range(1, num_teams + 1):
        tag = "  <-- YOU" if slot == USER_DRAFT_SLOT else ""
        print(f"\n--- Slot {slot} of {num_teams}{tag} ---")
        for entry in picks_by_slot[slot]:
            p = entry["player"]
            print(f"  Round {entry['round']:>2}, Pick {entry['overall']:>3}: "
                  f"{p.name:<24} ({p.position}, {p.team}) — ADP {p.adp:.1f}")


if __name__ == "__main__":
    pool = load_pool()
    have_projections = load_projections(pool, FANTASYPROS_DIR, PROJECTIONS_CSV_PATH)
    have_community = load_community_sheet(pool, COMMUNITY_SHEET_PATH)
    print_master_board(pool, top_n=60)
    print_positional_boards(pool)
    if have_projections:
        print_value_flags(pool)
    else:
        print("\n(No projections found — running ADP-only mode.)")
    if have_community:
        print_community_comparison(pool)
    if have_projections:
        print_draft_strategy(pool)
    draft_log, final_teams = simulate_draft(pool)
    print_all_slots_draft_plan(draft_log)
    print_user_draft_plan(draft_log)
    print("\n" + "=" * 78)
    print(f"YOUR FULL SIMULATED ROSTER ({BENCH_SLOTS} bench slots)")
    print("=" * 78)
    for p in final_teams[USER_DRAFT_SLOT].roster:
        print(f"  {p.position:<4} {p.name:<24} {p.team:<4} ADP {p.adp:.1f}")