"""Constrói os dados das ligas novas para o GoFoot Tools.

Lê o players.csv (NUNCA o altera), os ratings da EA FC e os plantéis do Transfermarkt, e escreve em --out:
  players_new.csv    as linhas que já tinham OVER ficam intactas; os jogadores sem nada são completados
                     (OVER, TAL, atributos, pé, posição, valor, salário); os que faltam no CSV são acrescentados
  leagues_add.json   clubes por país/liga, com o nome escrito no CSV (usado por update_leagues_js.py)
  report.json        diagnósticos (já avaliados noutro clube, cortes, guarda-redes acrescentados...)

Uso:
    python tools/build_leagues.py --csv players.csv --ea tools/work/ea_all.json \
        --tm tools/work/tm_squads.json --out tools/work/out

Opções úteis: --dry (não escreve nada), --diag (imprime casos duvidosos e o top por OVER),
--today AAAA-MM-DD (data usada para as idades), --pre (snapshot do players.csv anterior à geração por FM).
"""
import argparse
import collections
import datetime
import difflib
import hashlib
import json
import math
import os
import random
import re
import statistics
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gofoot_formulas as G  # noqa: E402
from common import *  # noqa: E402,F401,F403
from common import _lev1  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--csv", required=True, help="players.csv de partida (só leitura)")
ap.add_argument("--ea", default=None,
                help="json criado por fetch_ea.py (opcional: as ligas com \"ratings\": \"fm\" no config não precisam dele)")
ap.add_argument("--tm", required=True, help="json criado por fetch_transfermarkt.py")
ap.add_argument("--out", required=True, help="pasta de saída")
ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
ap.add_argument("--leagues-js", default=os.path.join(HERE, "..", "frontend", "leagues.js"))
ap.add_argument("--pre", default=None,
                help="players.csv anterior ao commit 855cdaa (por defeito lê-se do git: git show 855cdaa^:players.csv)")
ap.add_argument("--today", default=None, help="AAAA-MM-DD (por defeito, hoje)")
ap.add_argument("--seed", type=int, default=20261014, help="semente dos Ids novos")
ap.add_argument("--dry", action="store_true")
ap.add_argument("--diag", action="store_true")
ARGS = ap.parse_args()
CSV_IN, EA_PATH, TM_PATH, OUT_DIR = ARGS.csv, ARGS.ea, ARGS.tm, ARGS.out
DRY, DIAG = ARGS.dry, ARGS.diag
TODAY = datetime.date.fromisoformat(ARGS.today) if ARGS.today else datetime.date.today()
CONFIG = json.load(open(ARGS.config, encoding="utf-8"))
PRE_COMMIT = "855cdaa"  # commit que gerou OVER a partir do FM: o ficheiro anterior serve de calibração
os.makedirs(OUT_DIR, exist_ok=True)
SM = difflib.SequenceMatcher


def H(key, mod):
    return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % mod


# =============================================================================== load CSV
raw = open(CSV_IN, "rb").read().decode("latin-1")
ends_nl = raw.endswith("\r\n")
lines = raw.split("\r\n")
if ends_nl:
    lines.pop()
assert split_raw(lines[0]) == COLS, "unexpected header"
header_line, body = lines[0], lines[1:]


class Row:
    __slots__ = ("i", "name", "toks", "age", "club", "club_n", "isos", "grp", "rated", "rating", "pot", "id",
                 "nation", "position", "value", "over")


def pct(s):
    m = re.match(r"\s*([\d.]+)%", s or "")
    return float(m.group(1)) if m else None


def to_int(s):
    s = (s or "").strip()
    return int(s) if s.lstrip("-").isdigit() else None


rows = []
for i, line in enumerate(body):
    f = split_raw(line)
    if len(f) != 32:
        raise SystemExit(f"line {i + 2}: {len(f)} fields")
    r = Row()
    r.i = i
    r.name = unquote(f[CI["Name"]])
    r.toks = eff_tokens(r.name)
    r.age = to_int(unquote(f[CI["Age"]]))
    r.club = unquote(f[CI["Club"]])
    r.club_n = slug(r.club)
    r.nation = unquote(f[CI["Nation"]])
    r.isos = csv_nation_to_isos(r.nation)
    r.position = unquote(f[CI["Position"]])
    r.grp = G.posicao_grupo(unquote(f[CI["Posicao"]]) or r.position)
    r.over = to_int(unquote(f[CI["OVER"]]))
    r.rated = r.over is not None
    r.rating = pct(unquote(f[CI["Best Rating"]]))
    r.pot = pct(unquote(f[CI["Best Pot Rating"]]))
    r.id = unquote(f[CI["Id"]])
    v = unquote(f[CI["Value"]]).replace(",", "").strip()
    r.value = int(v) if v.isdigit() else None
    rows.append(r)
print(f"CSV rows: {len(rows)} | rated: {sum(r.rated for r in rows)}")
existing_ids = {r.id for r in rows}

tok_idx = collections.defaultdict(list)
pre_idx = collections.defaultdict(list)
rows_by_club = collections.defaultdict(list)
for r in rows:
    rows_by_club[r.club_n].append(r.i)
    for t in set(r.toks):
        tok_idx[t].append(r.i)
        if len(t) >= 5:
            pre_idx[t[:5]].append(r.i)

# =============================================================================== load EA + TM
ea = json.load(open(EA_PATH, encoding="utf-8")) if EA_PATH else []
ea_by_dob = collections.defaultdict(list)
for p in ea:
    m = re.match(r"(\d+)/(\d+)/(\d+)", p.get("birth") or "")
    p["dob"] = f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None
    p["name_sets"] = [eff_tokens((p["first"] or "") + " " + (p["last"] or ""))]
    if p["common"]:
        p["name_sets"].append(eff_tokens(p["common"]))
    p["name_sets"] = [n for n in p["name_sets"] if n]
    p["iso"] = ea_nat_to_iso(p["nat"])
    if p["dob"]:
        ea_by_dob[p["dob"]].append(p)
        y, mo, d = map(int, p["dob"].split("-"))
        p["age"] = TODAY.year - y - ((TODAY.month, TODAY.day) < (mo, d))
    else:
        p["age"] = None
ea_name_idx = collections.defaultdict(list)
for p in ea:
    for ns in p["name_sets"]:
        ea_name_idx[" ".join(sorted(ns))].append(p)

tm = json.load(open(TM_PATH, encoding="utf-8"))

# =============================================================================== EA -> GoFoot scale
def ea_to_over_raw(x):
    """EA OVR -> GoFoot OVER (same scale, slight compression at the top)."""
    return x - clamp((x - 76) / 5.0, 0, 1.5)


def age_adj(age):
    """Human-made GoFoot rows sit ~+1 above the mapped EA rating for youngsters and ~-1.6 for veterans."""
    return clamp((26 - age) * 0.15, -1.6, 1.0)


def ea_over(x, age):
    return int(clamp(G.js_round(ea_to_over_raw(x) + age_adj(age)), 40, 90))



# =============================================================================== club naming (leagues.js + CSV)
# Rated rows that already carry a club name keep counting for it: use that spelling when it exists.
rated_clubs = collections.Counter(r.club for r in rows if r.rated)
VARIANTS = CONFIG.get("club_name_variants", {})
LG_CFG = {(lg["country"], lg["league"]): lg for lg in CONFIG["leagues"]}
CLUB_CFG = {w["tm_id"]: w for lg in CONFIG["leagues"] for w in lg.get("clubs", [])}  # lista de clubes pedida no config
for c in tm:
    c["name"] = c["name"].strip()
    best, best_n = c["name"], rated_clubs.get(c["name"], 0)
    for v in VARIANTS.get(c["name"], []):
        if rated_clubs.get(v, 0) > best_n:
            best, best_n = v, rated_clubs[v]
    if c["id"] in CLUB_CFG:  # o config manda no nome com que o clube entra no site
        best = CLUB_CFG[c["id"]]["name"]
    best = to_latin1(best)  # o CSV é ISO-8859-1: o leagues.js tem de levar a mesma grafia (o site junta clubes pelo nome)
    c["csv_name"] = best
    c["csv_slug"] = slug(best)
    c["lg_cfg"] = LG_CFG.get((c["country"], c["league"]), {})
assert all(n == 1 for n in collections.Counter(c["csv_slug"] for c in tm).values())
leagues_js = load_leagues_js(ARGS.leagues_js)
being_built = {(c["country"], c["site_label"]) for c in tm}  # ligas que este build acrescenta (já podem estar no leagues.js)
covered = {slug(cn) for country, ls in leagues_js.items() for label, cl in ls.items()
           if (country, label) not in being_built for cn in cl}
clashes = [c["csv_name"] for c in tm if c["csv_slug"] in covered]
assert not clashes, "nome de clube igual ao de outra liga do leagues.js (o site junta os dois): %s" % clashes

# =============================================================================== matching TM <-> CSV
tm_players = []
KEEP = {}  # a player listed by two clubs (he moved during the season) stays with the club he joined last


def joined_key(p):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", p.get("joined") or "")
    return m.group(3) + m.group(2) + m.group(1) if m else ""


for c in tm:
    for p in c["players"]:
        k = KEEP.get(p["tm_id"])
        if k is None or joined_key(p) > joined_key(k[1]):
            KEEP[p["tm_id"]] = (c, p)
dup_players = 0
for c in tm:
    for p in c["players"]:
        if KEEP[p["tm_id"]][0] is not c or KEEP[p["tm_id"]][1] is not p:
            dup_players += 1
            continue
        q = dict(p)
        q["club"] = c
        q["toks"] = eff_tokens(p["name"])
        q["isos"] = {en_to_iso(n) for n in p["nats"] if en_to_iso(n)}
        q["grp"] = TM_GROUP.get(p["pos"])
        q["key"] = f"{c['id']}:{p['tm_id']}"
        q["match"] = None
        tm_players.append(q)
print("TM players:", len(tm_players), "| listed by two clubs (kept with the latest):", dup_players)


def surname_tokens(name):
    part = name.split(",")[0] if "," in name else (name.strip().split() or [""])[-1]
    return set(eff_tokens(part)) or set(tokens(part))


def surname_shared(a, b):
    return any(tok_eq(x, y) for x in surname_tokens(a) for y in surname_tokens(b))


def club_key(s):
    return frozenset(t for t in tokens(s) if t not in GENERIC_CLUB)


def club_pool_names(club):
    """FM club strings (slugs) that belong to the club. A club listed in the config with "fm" uses only those."""
    names = set(aliases.get(club["id"], ()))
    return sorted(names if club["id"] in seed_aliases else names | {club["csv_slug"]})


def club_bonus(q, r, aliases):
    cid = q["club"]["id"]
    if (r.club_n == q["club"]["csv_slug"] and cid not in seed_aliases) or r.club_n in aliases.get(cid, ()):
        return 25
    sf = q.get("signed_from")
    if sf and club_key(sf) and club_key(sf) == club_key(r.club):
        return 20
    return 0


def candidates(q):
    T = q["toks"]
    if not T:
        return []
    cnt = collections.Counter()
    for t in T:
        seen = set(tok_idx.get(t, ()))
        if len(t) >= 5:
            seen |= set(pre_idx.get(t[:5], ()))
        for i in seen:
            cnt[i] += 1
    need = 1 if len(T) == 1 else 2
    out = {i for i, c in cnt.items() if c >= need}
    if len(T) >= 2:  # one shared token: only mononym rows or surname+initial candidates
        out |= {i for i, c in cnt.items() if c == 1}
    return list(out)


def score_pair(q, r, aliases):
    ns = name_sim(q["toks"], r.toks)
    if ns < 0.55:
        return None
    if ns == 0.6 and not surname_shared(q["name"], r.name):
        return None  # first-name-only overlap (Tiago Morais vs Tiago Mamede)
    s = 100 * ns
    if r.age is not None and q["age"] is not None:
        d = q["age"] - r.age
        s += {1: 25, 0: 15, 2: 15}.get(d, -20 if d == -1 else -60)
    if q["isos"] and r.isos:
        s += 20 if (q["isos"] & r.isos) else -25
    cb = club_bonus(q, r, aliases)
    s += cb
    if q["grp"] and r.grp:
        if (q["grp"] == "G") != (r.grp == "G"):
            s -= 50
        elif q["grp"] == r.grp:
            s += 10
    val_ok = False
    if r.value and q["value"] and r.value > 100000 and q["value"] > 100000:
        lr = abs(math.log10(r.value / q["value"]))
        if lr <= 0.5:
            s += 8
            val_ok = True
        elif lr >= 1.0:
            s -= 8
    mono = len(q["toks"]) == 1 and len(r.toks) == 1
    if (ns < 0.9 or mono) and not (cb or val_ok):
        return None  # weak name evidence needs club or market-value corroboration
    return s


def match_all(aliases):
    pairs, per_player = [], {}
    for q in tm_players:
        scored = []
        for i in candidates(q):
            s = score_pair(q, rows[i], aliases)
            if s is not None and s >= 90:
                scored.append((s, i))
        scored.sort(reverse=True)
        per_player[q["key"]] = scored
        for s, i in scored[:6]:
            pairs.append((s, q["key"], i))
    pairs.sort(key=lambda x: -x[0])
    used, assigned = set(), {}
    for s, k, i in pairs:
        if k in assigned or i in used or s < 105:
            continue
        assigned[k] = (i, s)
        used.add(i)
    return assigned, per_player, used


# grafias do clube no FM indicadas no config ("fm": [...]): quando existem, são as únicas que contam para esse clube
seed_aliases = {cid: {slug(a) for a in w.get("fm", ())} for cid, w in CLUB_CFG.items() if "fm" in w}
print("matching pass 1 ...")
assigned, per_player, used_rows = match_all(seed_aliases)
by_key = {q["key"]: q for q in tm_players}
alias = collections.defaultdict(collections.Counter)
for k, (i, s) in assigned.items():
    if s >= 135 and not rows[i].rated:
        alias[by_key[k]["club"]["id"]][rows[i].club_n] += 1
aliases = {cid: {c for c, n in cnt.items() if n >= 3 and c not in ("", "-")} for cid, cnt in alias.items()}
aliases.update(seed_aliases)
print("matching pass 2 (with FM club aliases) ...")
assigned, per_player, used_rows = match_all(aliases)
for k, (i, s) in assigned.items():
    by_key[k]["match"], by_key[k]["match_score"] = rows[i], s

# stage 3: players still unmatched -> look inside the club's own FM rows with a looser, char-level name test
stage3 = 0
for q in tm_players:
    if q["match"] is not None:
        continue
    pool_clubs = club_pool_names(q["club"])
    best, second = None, None
    qn = " ".join(sorted(tokens(q["name"])))
    for cs in pool_clubs:
        for i in rows_by_club.get(cs, ()):
            r = rows[i]
            if i in used_rows or r.age is None or q["age"] is None or (q["age"] - r.age) not in (0, 1, 2):
                continue
            if q["grp"] and r.grp and (q["grp"] == "G") != (r.grp == "G"):
                continue
            if q["isos"] and r.isos and not (q["isos"] & r.isos):
                continue
            ratio = SM(None, qn, " ".join(sorted(tokens(r.name)))).ratio()
            if ratio >= 0.72 and (best is None or ratio > best[0]):
                best, second = (ratio, i), best
            elif ratio >= 0.72 and (second is None or ratio > second[0]):
                second = (ratio, i)
    if best and (second is None or best[0] - second[0] >= 0.08):
        q["match"], q["match_score"] = rows[best[1]], 100 * best[0]
        used_rows.add(best[1])
        stage3 += 1
print("stage-3 (club-context fuzzy) matches:", stage3)

# =============================================================================== match TM <-> EA
ea_stat = collections.Counter()
for q in tm_players:
    q["ea"] = None
    scored = []
    for p in ea_by_dob.get(q["dob"], []) if q["dob"] else []:
        ns = max((name_sim(q["toks"], n_) for n_ in p["name_sets"]), default=0.0)
        cr = max((SM(None, " ".join(sorted(q["toks"])), " ".join(sorted(n_))).ratio() for n_ in p["name_sets"]), default=0.0)
        nat_ok = bool(q["isos"] and p["iso"] and p["iso"] in q["isos"])
        scored.append((ns, cr, nat_ok, p))
    # same birth date AND some name evidence (a shared nationality alone is not enough: Olise vs Simbakoli)
    ok = [x for x in scored if x[0] >= 0.55 or (x[2] and x[1] >= 0.6)]
    if ok:
        q["ea"] = max(ok, key=lambda x: x[0] + 0.25 * x[2] + 0.3 * x[1])[3]
        ea_stat["by_dob"] += 1
    else:
        hits = [p for n_ in {" ".join(sorted(q["toks"]))} for p in ea_name_idx.get(n_, [])
                if p["age"] == q["age"] and q["isos"] and p["iso"] in q["isos"]]
        if len({p["id"] for p in hits}) == 1:
            q["ea"] = hits[0]
            ea_stat["by_name_age_nat"] += 1
        else:
            ea_stat["none"] += 1
print("EA match stats:", dict(ea_stat))

# duplicate guard: a stricter test so we never create a second rated copy of someone already rated
dup_guard = 0
for q in tm_players:
    m = q["match"]
    if m is None or m.rated:
        continue
    for s, i in per_player[q["key"]]:
        r = rows[i]
        if not r.rated or r.i == m.i:
            continue
        ns = name_sim(q["toks"], r.toks)
        age_ok = r.age is not None and q["age"] is not None and (q["age"] - r.age) in (0, 1, 2)
        nat_ok = not (q["isos"] and r.isos) or bool(q["isos"] & r.isos)
        strong = (ns >= 0.92 and len(q["toks"]) >= 2 and len(r.toks) >= 2) or (ns >= 0.9 and club_bonus(q, r, aliases) > 0)
        ea_ok = True
        if q["ea"] is not None and r.over is not None:
            ea_ok = abs(r.over - ea_over(q["ea"]["ovr"], q["age"] or 25)) <= 8
        if strong and age_ok and nat_ok and ea_ok:
            q["match"], q["match_score"] = r, s
            dup_guard += 1
            break
print("duplicate guard re-pointed to rated rows:", dup_guard)
stat = collections.Counter("none" if q["match"] is None else ("rated" if q["match"].rated else "fm") for q in tm_players)
print("TM <-> CSV matches:", dict(stat))


# =============================================================================== calibration from existing data
def load_pre_ids():
    """Ids que já tinham OVER antes da geração por FM (os feitos à mão), para isolar as linhas geradas."""
    if ARGS.pre:
        text = open(ARGS.pre, encoding="latin-1", newline="").read()
    else:
        repo = os.path.abspath(os.path.join(HERE, ".."))
        res = subprocess.run(["git", "-C", repo, "show", PRE_COMMIT + "^:players.csv"], capture_output=True)
        if res.returncode != 0:
            raise SystemExit("não consegui ler o players.csv de %s^ no git; usa --pre com um snapshot" % PRE_COMMIT)
        text = res.stdout.decode("latin-1")
    ids = set()
    for ln in text.replace("\r\n", "\n").split("\n")[1:]:
        if ln:
            f = split_raw(ln)
            if len(f) == 32 and unquote(f[CI["OVER"]]).strip():
                ids.add(unquote(f[CI["Id"]]))
    return ids


pre_ids_with_over = load_pre_ids()
assert len(pre_ids_with_over) > 10000, "snapshot anterior mal lido"
gen_rows = [r for r in rows if r.rated and r.id not in pre_ids_with_over and r.rating is not None and r.pot is not None]
tal_of = {r.i: to_int(unquote(split_raw(body[r.i])[CI["TAL"]])) for r in gen_rows}
gen_rows = [r for r in gen_rows if r.over is not None and tal_of.get(r.i) is not None]
print("calibration rows (previous FM-based pass):", len(gen_rows))


def build_map(pairs, step=2.0, min_n=4):
    b = collections.defaultdict(list)
    for x, y in pairs:
        b[math.floor(x / step) * step].append(y)
    pts = [(k + step / 2, statistics.median(v), len(v)) for k, v in sorted(b.items()) if len(v) >= min_n]
    return isotonic(pts)


FM_OVER, FM_TAL = {}, {}
for g_ in G.GRUPOS_VALIDOS:
    sub = [r for r in gen_rows if r.grp == g_]
    if len(sub) < 40:
        sub = gen_rows
    FM_OVER[g_] = build_map([(r.rating, r.over) for r in sub])
    FM_TAL[g_] = build_map([(r.pot, tal_of[r.i]) for r in sub])


def fm_over(grp, rating):
    return interp(FM_OVER[grp], rating, 0.8, 0.8)


def fm_tal(grp, pot):
    return interp(FM_TAL[grp], pot, 0.75, 0.75)


# TAL - OVER by group and age (stars and regulars) from every rated row, for players without FM potential
gap_tab = collections.defaultdict(list)
for r in rows:
    if r.rated and r.grp and r.age:
        tal_v = to_int(unquote(split_raw(body[r.i])[CI["TAL"]]))
        if tal_v is not None:
            b = 0 if r.age <= 19 else 1 if r.age <= 22 else 2 if r.age <= 25 else 3 if r.age <= 29 else 4
            gap_tab[(r.grp, b)].append(tal_v - r.over)
TAL_GAP = {k: statistics.median(v) for k, v in gap_tab.items() if len(v) >= 8}
TAL_REF_CAP = CONFIG["tal_ref_cap"]
TAL_PIN = CONFIG.get("tal_pins", {})

# attribute models ---------------------------------------------------------------------------------------
OUTF = ["pac", "sho", "pas", "dri", "def", "phy", "reactions", "composure", "vision"]
GKF = ["gkDiving", "gkHandling", "gkKicking", "gkPositioning", "gkReflexes", "reactions"]
ATTRS_OUT = ["TEC", "ATA", "DEF", "FIS", "MEN"]
ATTRS_GK = ["REF", "POS", "AER", "SAI", "MEN"]
COLMAP = {"TEC": "TEC", "ATA": "ATA", "DEF": "DEF", "FIS": "FIS", "MEN": "MEN", "REF": "REF", "POS": "POS_GK",
          "AER": "AER", "SAI": "SAI"}


def row_attrs(r):
    f = split_raw(body[r.i])
    return {a: to_int(unquote(f[CI[COLMAP[a]]])) for a in COLMAP}


neigh = collections.defaultdict(list)
ea_train = collections.defaultdict(list)
for r in rows:
    if not r.rated or not r.grp:
        continue
    at = row_attrs(r)
    keys = G.attr_keys(r.grp)
    if any(at.get(k) is None for k in keys):
        continue
    exact = sum(at[k] * w for k, w in G.OVER_WEIGHTS[r.grp].items())
    neigh[r.grp].append((exact, r.age or 25, {k: at[k] - exact for k in keys}))
    cands = [p for p in ea_name_idx.get(" ".join(sorted(r.toks)), [])
             if p["age"] is not None and r.age is not None and abs(p["age"] - r.age - 1) <= 2]
    if len({p["id"] for p in cands}) == 1:
        p = cands[0]
        if abs(round(exact) - ea_over(p["ovr"], r.age)) <= 4:
            ea_train[r.grp].append((p["stats"], at))


def solve(A, b):
    n = len(b)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r_: abs(M[r_][i]))
        M[i], M[piv] = M[piv], M[i]
        for r_ in range(i + 1, n):
            f = M[r_][i] / M[i][i]
            for c in range(i, n + 1):
                M[r_][c] -= f * M[i][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def fit_ridge(X, y, lam):
    n, k = len(X), len(X[0])
    mx = [sum(X[i][j] for i in range(n)) / n for j in range(k)]
    my = sum(y) / n
    Xc = [[X[i][j] - mx[j] for j in range(k)] for i in range(n)]
    A = [[sum(Xc[i][a] * Xc[i][b] for i in range(n)) + (lam if a == b else 0) for b in range(k)] for a in range(k)]
    b = [sum(Xc[i][a] * (y[i] - my) for i in range(n)) for a in range(k)]
    w = solve(A, b)
    return w, my - sum(w[j] * mx[j] for j in range(k))


POOL = {"Z": ["Z", "L", "V"], "L": ["L", "Z", "V"], "V": ["V", "M", "L", "Z"], "M": ["M", "V", "PE", "PD"],
        "PE": ["PE", "PD", "CA", "M"], "PD": ["PD", "PE", "CA", "M"], "CA": ["CA", "PE", "PD"], "G": ["G"]}
EA_MODEL = {}
for g_ in G.GRUPOS_VALIDOS:
    feats = GKF if g_ == "G" else OUTF
    attrs = ATTRS_GK if g_ == "G" else ATTRS_OUT
    sample = []
    for gg in POOL[g_]:
        sample += ea_train.get(gg, [])
        if len(sample) >= 200:
            break
    sample = [(s, a) for s, a in sample if all(a.get(k) is not None for k in attrs)]
    if len(sample) < 25:
        EA_MODEL[g_] = None
        continue
    X = [[float(s.get(f_, 0)) for f_ in feats] for s, _ in sample]
    model = {k: fit_ridge(X, [float(a[k]) for _, a in sample], 8.0 * len(sample) / 100) for k in attrs}
    EA_MODEL[g_] = (feats, attrs, model, len(sample))
print("EA attribute models (training sizes):", {g_: (m[3] if m else None) for g_, m in EA_MODEL.items()})


def finalize_attrs(grp, floats, target):
    keys = G.attr_keys(grp)
    w = G.OVER_WEIGHTS[grp]
    cur = {k: int(clamp(G.js_round(floats[k]), 10, 99)) for k in keys}
    guard = 0
    while G.calcular_over(grp, cur) != target and guard < 300:
        guard += 1
        total = sum(cur[k] * w[k] for k in keys)
        up = total < target
        cand = sorted(keys, key=lambda k: (floats[k] - cur[k]) * (1 if up else -1), reverse=True)
        for k in cand:
            nv = cur[k] + (1 if up else -1)
            if 10 <= nv <= 99:
                cur[k] = nv
                break
        else:
            break
    return cur


def attrs_from_ea(grp, p, target):
    m = EA_MODEL.get(grp)
    if not m or not p:
        return None
    feats, attrs, model, _n = m
    pred = {}
    for k in attrs:
        w_, b0 = model[k]
        pred[k] = b0 + sum(w_[j] * float(p["stats"].get(f_, 0)) for j, f_ in enumerate(feats))
    keys = G.attr_keys(grp)
    shift = target - sum(pred[k] * G.OVER_WEIGHTS[grp][k] for k in keys)
    return finalize_attrs(grp, {k: pred[k] + shift for k in keys}, target)


def attrs_from_neighbour(grp, target, age, seed):
    pool = neigh.get(grp) or []
    scored = sorted(pool, key=lambda t: abs(t[0] - target) + 0.25 * abs(t[1] - age))[:15]
    exact, _a, off = scored[H(seed, len(scored))]
    return finalize_attrs(grp, {k: target + off[k] for k in G.attr_keys(grp)}, target)


# =============================================================================== OVER sources
def age_bucket(a):
    return 0 if a <= 19 else 1 if a <= 22 else 2 if a <= 26 else 3


pairs_bias = collections.defaultdict(list)
for q in tm_players:
    m = q["match"]
    if q["ea"] and m is not None and not m.rated and m.rating is not None and q["age"]:
        grp = q["grp"] or "M"
        pairs_bias[age_bucket(q["age"])].append(ea_over(q["ea"]["ovr"], q["age"]) - G.js_round(clamp(fm_over(grp, m.rating), 40, 90)))
FM_BIAS = {b: statistics.median(v) for b, v in pairs_bias.items() if len(v) >= 20}
pairs_lg = collections.defaultdict(list)
for q in tm_players:
    m = q["match"]
    if q["ea"] and m is not None and not m.rated and m.rating is not None and q["age"]:
        pairs_lg[(q["club"]["country"], age_bucket(q["age"]))].append(
            ea_over(q["ea"]["ovr"], q["age"]) - G.js_round(clamp(fm_over(q["grp"] or "M", m.rating), 40, 90)))


def fm_corr(country, age):
    """Correction (EA scale minus FM-derived) for a player without an EA rating: league-specific, shrunk to the global one."""
    ab = age_bucket(age)
    g = FM_BIAS.get(ab, 0)
    v = pairs_lg.get((country, ab), [])
    if len(v) < 8:
        return g
    k = 20.0
    return (len(v) * statistics.median(v) + k * g) / (len(v) + k)


if DIAG:
    cell = collections.defaultdict(list)
    for q in tm_players:
        m = q["match"]
        if q["ea"] and m is not None and not m.rated and m.rating is not None and q["age"]:
            grp = q["grp"] or "M"
            fb = "<60" if m.rating < 60 else "60-65" if m.rating < 65 else "65-70" if m.rating < 70 else "70-75" if m.rating < 75 else "75+"
            cell[(age_bucket(q["age"]), fb)].append(ea_over(q["ea"]["ovr"], q["age"]) - G.js_round(clamp(fm_over(grp, m.rating), 40, 90)))
    print("FM correction cells (age bucket x FM rating): n / median(EA-derived minus FM-derived)")
    for ab, name in enumerate(["<=19", "20-22", "23-26", "27+"]):
        print("   ", name.ljust(6), "  ".join(f"{fb}: n={len(cell[(ab, fb)]):3} {statistics.median(cell[(ab, fb)]) if cell[(ab, fb)] else float('nan'):+.1f}" for fb in ["<60", "60-65", "65-70", "70-75", "75+"]))
if DIAG:
    lg = collections.defaultdict(list)
    for q in tm_players:
        m = q["match"]
        if q["ea"] and m is not None and not m.rated and m.rating is not None and q["age"]:
            grp = q["grp"] or "M"
            lg[(q["club"]["country"], age_bucket(q["age"]))].append(ea_over(q["ea"]["ovr"], q["age"]) - G.js_round(clamp(fm_over(grp, m.rating), 40, 90)))
    print("EA-derived minus FM-derived by league and age bucket (n/median):")
    for country in sorted({c["country"] for c in tm}):
        print("   ", country.ljust(11), "  ".join(f"{nm}: n={len(lg[(country, ab)]):3} {statistics.median(lg[(country, ab)]) if lg[(country, ab)] else float('nan'):+.1f}" for ab, nm in enumerate(["<=19", "20-22", "23-26", "27+"])))
print("FM->EA correction by age bucket (<=19, 20-22, 23-26, 27+):", {b: FM_BIAS.get(b, 0) for b in range(4)},
      {b: len(pairs_bias[b]) for b in range(4)})

val_pairs = [(q["value"], q["age"], ea_over(q["ea"]["ovr"], q["age"])) for q in tm_players
             if q["ea"] and q["value"] and q["age"]]
VAL_EDGES = [0, 1e5, 2.5e5, 5e5, 1e6, 2.5e6, 5e6, 1e7, 2.5e7, 5e7, 1e8, 1e12]
VAL_TAB = {}
for ab, (lo, hi) in enumerate([(0, 21), (22, 29), (30, 99)]):
    for vb in range(len(VAL_EDGES) - 1):
        v = [o for val, a, o in val_pairs if lo <= a <= hi and VAL_EDGES[vb] <= val < VAL_EDGES[vb + 1]]
        VAL_TAB[(ab, vb)] = statistics.median(v) if len(v) >= 5 else None


def over_from_value(value, age):
    ab = 0 if age <= 21 else 1 if age <= 29 else 2
    if not value:
        return 52
    vb = max(i for i in range(len(VAL_EDGES) - 1) if VAL_EDGES[i] <= value)
    for d in (0, 1, -1, 2, -2, 3, -3):
        c = VAL_TAB.get((ab, vb + d))
        if c is not None:
            return int(round(c))
    return 55


# =============================================================================== leagues without EA ratings ("ratings": "fm")
# The FM rating of the league's own players is turned into a z-score and put on the OVER distribution asked for in
# the config (over_target: mean, sd, min, max). Players without an FM rating take the median of players with the same
# market value, or a reproducible draw around the mean when they have none.
FM_LEAGUES = {k: lg for k, lg in LG_CFG.items() if lg.get("ratings") == "fm"}
FM_TARGET, FM_STATS, FM_VAL = {}, {}, {}
FM_VAL_EDGES = [0, 5e4, 1e5, 2e5, 3e5, 5e5, 1e6, 1e12]


def unit_normal(key):
    """Reproducible standard-normal number for a key (Box-Muller over an md5 hash)."""
    h = hashlib.md5(key.encode("utf-8")).digest()
    u1 = (int.from_bytes(h[:6], "big") + 1) / (2 ** 48 + 1)
    u2 = int.from_bytes(h[6:12], "big") / 2 ** 48
    return math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)


def fm_league_over(lk, grp, rating):
    T = FM_TARGET[lk]
    mu, sd = FM_STATS[lk].get(grp) or FM_STATS[lk]["*"]
    z = (rating - mu) / max(sd, 1.0)
    return int(clamp(G.js_round(T["mean"] + z * T["sd"]), T["min"], T["max"]))


def fm_league_tal(lk, grp, over, rating, pot):
    """Potential gap of the FM rows, on the same (compressed) scale as the OVER."""
    _mu, sd = FM_STATS[lk].get(grp) or FM_STATS[lk]["*"]
    return over + max(0.0, fm_tal(grp, pot) - fm_over(grp, rating)) * FM_TARGET[lk]["sd"] / max(sd, 1.0)


def fm_league_nofm(lk, q, age):
    """OVER of a player without an FM rating."""
    T = FM_TARGET[lk]
    base = None
    if q["value"]:
        vb = max(i for i in range(len(FM_VAL_EDGES) - 1) if FM_VAL_EDGES[i] <= q["value"])
        for d in (0, 1, -1, 2, -2, 3, -3):
            if FM_VAL[lk].get(vb + d) is not None:
                base = FM_VAL[lk][vb + d]
                break
    if base is None:
        base = T["mean"] - 1.0 + 0.7 * T["sd"] * unit_normal(q["key"])
    base += {16: -3, 17: -2.5, 18: -2, 19: -1, 20: -0.5}.get(age, 0)
    return int(clamp(G.js_round(base), T["min"], T["max"]))


for lk, lg in FM_LEAGUES.items():
    T = {"mean": 51.0, "sd": 3.8, "min": 42, "max": 60}
    T.update(lg.get("over_target", {}))
    FM_TARGET[lk] = T
    by_g = collections.defaultdict(list)
    for q in tm_players:
        m = q["match"]
        if (q["club"]["country"], q["club"]["league"]) == lk and m is not None and not m.rated and m.rating is not None:
            by_g[q["grp"] or m.grp or "M"].append(m.rating)
    allr = [x for v in by_g.values() for x in v]
    mu_all, sd_all = statistics.mean(allr), statistics.pstdev(allr)
    FM_STATS[lk] = {g: ((statistics.mean(v), statistics.pstdev(v)) if len(v) >= 40 else (mu_all, sd_all))
                    for g, v in by_g.items()}
    FM_STATS[lk]["*"] = (mu_all, sd_all)
    print(f"{lk[1]}: FM rating of {len(allr)} matched players: mean {mu_all:.1f} sd {sd_all:.1f} -> OVER target {T}")
    pts = collections.defaultdict(list)
    for q in tm_players:
        m = q["match"]
        if (q["club"]["country"], q["club"]["league"]) == lk and m is not None and not m.rated \
                and m.rating is not None and q["value"]:
            vb = max(i for i in range(len(FM_VAL_EDGES) - 1) if FM_VAL_EDGES[i] <= q["value"])
            pts[vb].append(fm_league_over(lk, q["grp"] or m.grp or "M", m.rating))
    FM_VAL[lk] = {vb: statistics.median(v) for vb, v in pts.items() if len(v) >= 8}


# =============================================================================== per-player plan
FOOT = {"right": "D", "left": "E", "both": "A"}
plan = []
diag = collections.Counter()
mismatch = []
for q in tm_players:
    club, m, ea_p = q["club"], q["match"], q["ea"]
    grp = q["grp"] or (EA_GROUP.get(ea_p["pos"]) if ea_p else None) or (m.grp if m else None) or "M"
    item = {"q": q, "grp": grp, "club": club, "row": m}
    if m is not None and m.rated:
        item["kind"] = "rated"
        if m.club_n != club["csv_slug"]:
            diag["rated_in_other_club"] += 1
        plan.append(item)
        continue
    if club["lg_cfg"].get("same_club_guard") and q["age"] is not None:
        # "same_club_guard": se o clube já tem uma linha avaliada com o mesmo nome e a mesma idade (±2), é a mesma pessoa
        # (o utilizador escreveu o nome de outra maneira): não se cria uma segunda linha
        twin = next((rows[i] for i in rows_by_club.get(club["csv_slug"], ())
                     if rows[i].rated and rows[i].age is not None and abs(rows[i].age - q["age"]) <= 2
                     and name_sim(q["toks"], rows[i].toks) >= 0.92), None)
        if twin is not None:
            item["kind"], item["row"] = "rated", twin
            diag["same_club_guard"] += 1
            plan.append(item)
            continue
    item["kind"] = "fm" if m is not None else "new"
    age = q["age"] if q["age"] is not None else (m.age + 1 if m and m.age else 25)
    item["age"] = age
    over_ea = ea_over(ea_p["ovr"], age) if ea_p else None
    over_fm = None
    if m is not None and m.rating is not None:
        raw_fm = G.js_round(clamp(fm_over(grp, m.rating), 40, 90))
        over_fm = int(clamp(G.js_round(raw_fm + fm_corr(club["country"], age)), 40, 90))
    lk = (club["country"], club["league"])
    if lk in FM_LEAGUES:
        if m is not None and m.rating is not None:
            over, src = fm_league_over(lk, grp, m.rating), "FM"
        else:
            over, src = fm_league_nofm(lk, q, age), "FMV"
    elif over_ea is not None:
        over, src = over_ea, "EA"
        if over_fm is not None and abs(over_fm - over_ea) >= 10:
            mismatch.append((q["name"], club["name"], over_ea, over_fm, m.name, m.club, m.rating))
    elif over_fm is not None:
        over, src = over_fm, "FM"
    else:
        over, src = over_from_value(q["value"], age) + {16: -7, 17: -5, 18: -3, 19: -1}.get(age, 0), "TM"
    over = int(clamp(over, 40, 90)) if lk not in FM_LEAGUES else over
    if club["lg_cfg"].get("over_shift"):  # nivelamento da liga no config (pontos de OVER, também para o TAL, o valor e o salário)
        over = int(clamp(over + club["lg_cfg"]["over_shift"], 40, 90))
    item["over"], item["over_src"] = over, src
    diag["over_" + src] += 1
    # TAL
    if m is not None and m.pot is not None and m.rating is not None:
        if lk in FM_LEAGUES:
            tal = fm_league_tal(lk, grp, over, m.rating, m.pot)
        else:
            tal = over + (fm_tal(grp, m.pot) - fm_over(grp, m.rating))
        tal_src = "FM"
    else:
        b = 0 if age <= 19 else 1 if age <= 22 else 2 if age <= 25 else 3 if age <= 29 else 4
        tal = over + TAL_GAP.get((grp, b), 0)
        tal_src = "age"
    if src == "TM" and age <= 19 and q["value"]:
        # for a prospect that only has a market value, the value says more about talent than about today's level
        tal = max(tal, over_from_value(q["value"], 22) + TAL_GAP.get((grp, 1), 2))
    cap = TAL_REF_CAP[grp] if age >= 22 else 94
    item["tal"] = int(clamp(G.js_round(tal), 40, cap))
    # references used when TAL was calibrated (commit 5b4747e): the best 22+ player of each position
    pin = TAL_PIN.get(q["name"])
    if pin is not None and age >= 22:
        item["tal"] = pin
    item["tal_src"] = tal_src
    # attributes
    attrs = attrs_from_ea(grp, ea_p, over) if ea_p else None
    item["attr_src"] = "EA"
    if attrs is None:
        attrs = attrs_from_neighbour(grp, over, age, q["key"])
        item["attr_src"] = "profile"
    assert G.calcular_over(grp, attrs) == over, (q["name"], grp, attrs, over)
    item["attrs"] = attrs
    foot = FOOT.get(q["foot"]) or (("E" if ea_p["foot"] == 2 else "D") if ea_p else None)
    item["pe"] = wing_foot(grp, foot or "D")
    item["valor"] = G.calcular_valor(grp, over, item["tal"], age, attrs.get("FIS"), attrs.get("MEN"))
    item["salario"] = G.calcular_salario(over, item["valor"])
    plan.append(item)
print("plan:", dict(collections.Counter(i["kind"] for i in plan)), "|", dict(diag))
print("EA vs FM disagreement >= 10:", len(mismatch))

# =============================================================================== squad caps and GK top-up
def club_pool_rows(club):
    """FM rows that belong to the club."""
    return [rows[i] for cs in club_pool_names(club) for i in rows_by_club.get(cs, ())]


by_club = collections.defaultdict(list)
for it in plan:
    by_club[it["club"]["id"]].append(it)
dropped, topped, gk_short, short_squads = [], [], [], []
for cid, items in by_club.items():
    club = items[0]["club"]
    if len(items) > 35:
        cand = sorted((it for it in items if it["kind"] in ("fm", "new") and it["grp"] != "G"),
                      key=lambda it: (it["q"]["value"] or 0, it["over"]))
        for it in cand[:len(items) - 35]:
            it["kind"] = "dropped"
            dropped.append((club["name"], it["q"]["name"]))
    gks = [it for it in items if it["grp"] == "G" and it["kind"] != "dropped"]
    if len(gks) < 3:
        pool = []
        if club["lg_cfg"].get("gk_topup", True):  # FM rows are a year old: leagues that want only current data turn it off
            pool = [r for r in club_pool_rows(club)
                    if not (r.i in used_rows or r.rated or r.grp != "G" or r.age is None or r.age > 22 or (r.rating or 0) < 50)]
        if pool:
            r = max(pool, key=lambda x: x.rating)
            used_rows.add(r.i)
            age = r.age + 1
            q = {"name": " ".join(reversed([t.strip() for t in r.name.split(",")])) if "," in r.name else r.name,
                 "age": age, "isos": r.isos, "grp": "G", "pos": "Goalkeeper", "foot": "", "value": r.value, "nats": [],
                 "ea": None, "club": club, "key": f"gk:{r.i}", "dob": None, "match": r}
            grp = "G"
            over = int(clamp(G.js_round(clamp(fm_over(grp, r.rating), 40, 90) + fm_corr(club["country"], age)
                                        + club["lg_cfg"].get("over_shift", 0)), 40, 90))
            tal = int(clamp(G.js_round(over + fm_tal(grp, r.pot) - fm_over(grp, r.rating)), 40, 94))
            attrs = attrs_from_neighbour(grp, over, age, q["key"])
            valor = G.calcular_valor(grp, over, tal, age, attrs.get("FIS"), attrs.get("MEN"))
            it = {"q": q, "grp": grp, "club": club, "row": r, "kind": "fm", "age": age, "over": over, "over_src": "FM",
                  "tal": tal, "tal_src": "FM", "attrs": attrs, "attr_src": "profile", "pe": "D", "valor": valor,
                  "salario": G.calcular_salario(over, valor)}
            plan.append(it)
            topped.append((club["name"], q["name"], r.age, r.rating))
        else:
            gk_short.append((club["name"], len(gks)))
    min_squad = club["lg_cfg"].get("min_squad", 0)
    if min_squad:
        members = (sum(it["kind"] in ("fm", "new") for it in items)
                   + sum(1 for i in rows_by_club.get(club["csv_slug"], ()) if rows[i].rated))
        if members < min_squad:
            short_squads.append((club["name"], members))
print("dropped by the 35-player cap:", dropped)
print("goalkeepers added from the club's FM rows:", topped)
print("clubs that stay below 3 GKs:", gk_short)
if short_squads:
    print(f"clubs below their minimum squad ({len(short_squads)}):", short_squads)

# =============================================================================== diagnostics
if DIAG:
    print("================ DIAGNOSTICS ================")
    n = 0
    print("--- rated rows (kept untouched) whose CSV club differs from the TM club:")
    for it in plan:
        if it["kind"] == "rated" and it["row"].club_n != it["club"]["csv_slug"]:
            q, r = it["q"], it["row"]
            n += 1
            if n <= 40:
                print(f"   TM {q['name']!r} @ {it['club']['name']!r} age={q['age']} {q['nats'][:1]} {q['pos']} | CSV {r.name!r} club={r.club!r} age={r.age} nat={r.nation!r} OVER={r.over} EA={q['ea']['ovr'] if q['ea'] else None} sc={q['match_score']:.0f}")
    print("--- players that will be appended (no CSV row):")
    news = [it for it in plan if it["kind"] == "new"]
    print("   count:", len(news))
    for it in news[:40]:
        q = it["q"]
        print(f"   {q['name']!r:28} {it['club']['name']!r:24} age={q['age']} {q['nats'][:1]} {q['pos']} EA={'y' if q['ea'] else 'n'} val={q['value']}")
    print("--- top 30 by OVER:")
    for it in sorted([i for i in plan if i["kind"] in ("fm", "new")], key=lambda it: (-it["over"], -it["tal"]))[:30]:
        q = it["q"]
        print(f"   {q['name']!r:26} {it['club']['name']!r:22} age={it['age']:2} {it['grp']:2} OVER={it['over']} TAL={it['tal']} {it['over_src']}/{it['tal_src']}/{it['attr_src']}")
    print("--- OVER distribution:", sorted(collections.Counter(it["over"] for it in plan if it["kind"] in ("fm", "new")).items()))
    print("--- lowest-score FM matches (most doubtful):")
    low = sorted([it for it in plan if it["kind"] == "fm"], key=lambda it: it["q"].get("match_score", 999))[:45]
    for it in low:
        q, r = it["q"], it["row"]
        print(f"   sc={q.get('match_score', 0):5.0f} TM {q['name']!r:26} {it['club']['name']!r:20} {q['age']} {q['nats'][:1]} {q['pos'][:10]:10} val={q['value']} | CSV {r.name!r:28} {r.club!r:20} {r.age} {r.nation!r:18} FMval={r.value} rt={r.rating}")
    print("--- random FM matches:")
    rnd = random.Random(7).sample([it for it in plan if it["kind"] == "fm"], 40)
    for it in rnd:
        q, r = it["q"], it["row"]
        print(f"   sc={q.get('match_score', 0):5.0f} TM {q['name']!r:26} {it['club']['name']!r:20} {q['age']} {q['nats'][:1]} | CSV {r.name!r:28} {r.club!r:20} {r.age} {r.nation!r:18}")
    print("--- players whose OVER came only from the Transfermarkt value:")
    for it in sorted([i for i in plan if i["kind"] in ("fm", "new") and i["over_src"] == "TM"], key=lambda it: -(it["q"]["value"] or 0)):
        q = it["q"]
        print(f"   {q['name']!r:28} {it['club']['name']!r:22} age={it['age']:2} {it['grp']:2} val={q['value']} -> OVER={it['over']} TAL={it['tal']}")
    print("--- EA vs FM disagreement sample:")
    for t in mismatch[:20]:
        print("   ", t)

# =============================================================================== write
if DRY:
    sys.exit(0)

rng = random.Random(ARGS.seed)
used_ids = set(existing_ids)


def new_id(name):
    base = re.sub(r"[^a-z0-9]+", "", strip_accents(name).lower()) or "jogador"
    while True:
        suffix = "".join(rng.choice("0123456789abcdefghijklmnopqrstuvwxyz") for _ in range(8))
        i = f"{base}_{suffix}"
        if i not in used_ids:
            used_ids.add(i)
            return i


def attr_fields(grp, attrs):
    out = {c: "" for c in ("TEC", "ATA", "DEF", "FIS", "MEN", "REF", "POS_GK", "AER", "SAI")}
    for k, v in attrs.items():
        out[COLMAP[k]] = str(v)
    return out


def fix_mangled_name(fm_name, tm_name, strict=False):
    """The FM export lost some characters ('Vlasic' -> 'Vlaaic', 'Redzic' -> 'Red~ic'). When the Transfermarkt name is the
    same name apart from 1-character differences or junk characters, use the Transfermarkt spelling. With strict=True
    (config "name_fix": "mangled") only names with letters the export cannot hold (s-caron, z-caron...) are touched, so
    different spellings of the same name ('Vitor' / 'Victor') stay as the FM has them."""
    if re.search(r"[~`^?]", fm_name):
        return reverter_nome(tm_name)
    a, b = tokens(tm_name), tokens(fm_name)
    if set(a) == set(b):
        return fm_name
    if strict and not any(ord(ch) > 255 for ch in tm_name):
        return fm_name
    for x in a:
        for y in b:
            if x != y and len(x) >= 5 and len(y) >= 5 and _lev1(x, y):
                return reverter_nome(tm_name)
    return fm_name


renamed = []
out_body = list(body)
appended = []
changed_idx = []
nat_unknown = collections.Counter()
for it in plan:
    if it["kind"] not in ("fm", "new"):
        continue
    q, club, grp = it["q"], it["club"], it["grp"]
    first_nat = q["nats"][0] if q["nats"] else None
    nation_pt = NATIONS[first_nat][1] if first_nat in NATIONS else None
    if first_nat and not nation_pt:
        nat_unknown[first_nat] += 1
    af = attr_fields(grp, it["attrs"])
    vals = {"Pe": it["pe"], "Posicao": grp, "TAL": str(it["tal"]), "Valor": str(it["valor"]),
            "OVER": str(it["over"]), "Salario": str(it["salario"]), **af}
    if it["kind"] == "fm":
        r = it["row"]
        f = split_raw(body[r.i])
        vals["Club"] = club["csv_name"]
        vals["Age"] = str(it["age"])
        fixed = fix_mangled_name(r.name, q["name"], club["lg_cfg"].get("name_fix") == "mangled")
        if fixed != r.name:
            vals["Name"] = fixed
            renamed.append((r.name, fixed))
        if nation_pt:
            vals["Nation"] = nation_pt
        for col, v in vals.items():
            f[CI[col]] = encode_field(v)
        out_body[r.i] = ";".join(f)
        changed_idx.append(r.i)
    else:
        name = q["name"]
        f = [""] * 32
        f[CI["Gen"]] = "M"
        base = {"Name": reverter_nome(name), "Nation": nation_pt or (first_nat or ""),
                "Position": TM_FM_POS.get(q["pos"], ""), "Club": club["csv_name"], "Age": str(it["age"]),
                "Id": new_id(name), **vals}
        for col, v in base.items():
            f[CI[col]] = encode_field(v)
        appended.append(";".join(f))
print("names restored from Transfermarkt:", len(renamed), renamed[:12])
print("rows completed:", len(changed_idx), "| rows appended:", len(appended), "| nations without a PT name:", dict(nat_unknown))

final_lines = [header_line] + out_body + appended
text = "\r\n".join(final_lines) + ("\r\n" if ends_nl else "")
open(os.path.join(OUT_DIR, "players_new.csv"), "wb").write(text.encode("latin-1"))

leagues_add = collections.OrderedDict()
for c in tm:
    leagues_add.setdefault(c["country"], collections.OrderedDict()).setdefault(c["league"], []).append(c["csv_name"])
json.dump(leagues_add, open(os.path.join(OUT_DIR, "leagues_add.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

report = {
    "counts": {"tm_players": len(tm_players), "kinds": dict(collections.Counter(i["kind"] for i in plan)), "diag": dict(diag)},
    "changed_row_indexes": changed_idx,
    "appended": len(appended),
    "mismatch": mismatch, "dropped": dropped, "gk_topped": topped, "gk_short": gk_short,
    "rated_in_other_club": [(it["q"]["name"], it["club"]["name"], it["row"].name, it["row"].club) for it in plan
                            if it["kind"] == "rated" and it["row"].club_n != it["club"]["csv_slug"]],
}
json.dump(report, open(os.path.join(OUT_DIR, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("written:", os.path.join(OUT_DIR, "players_new.csv"))
