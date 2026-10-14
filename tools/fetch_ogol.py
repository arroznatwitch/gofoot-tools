"""Cruza os plantéis do Transfermarkt com o elenco atual do ogol.com.br (clubes com "ogol" no config).

O Transfermarkt demora a tirar os jogadores que saem dos clubes pequenos do Brasil (acabou a época, acabou o contrato e
continuam lá como "atuais"). O ogol marca cada jogador do elenco como ativo ou inativo e a ficha dele diz qual é o clube
atual, por isso serve para limpar e completar:

  * jogador do Transfermarkt que o ogol marca como inativo no clube -> sai;
  * jogador do Transfermarkt que o ogol não conhece -> fica (não há nada que o contrarie);
  * jogador ativo no ogol que o Transfermarkt não tem -> entra, com data de nascimento, posição e nacionalidade da ficha
    dele no ogol; só entra se a ficha disser que o clube atual é este (um emprestado a outro clube não conta).

Uso:
    python tools/fetch_ogol.py --config tools/config_serie_d.json --tm tools/work/serie_d_tm.json \
        --out tools/work/serie_d_squads.json --cache-dir tools/work/ogol_raw --today 2026-10-14

As páginas ficam em cache e há uma pausa de ~1 s entre pedidos. O ogol não tem pé preferido nem valor de mercado:
os jogadores que vêm só dele ficam sem esses campos (o build usa "D" e calcula o resto).
"""
import argparse
import collections
import datetime
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import NATIONS, TM_GROUP, eff_tokens, name_sim, norm_text  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
BASE = "https://www.ogol.com.br"

# posição da ficha do ogol -> posição "à Transfermarkt" (a que o build já conhece)
POS_RULES = [
    ("goleiro", "Goalkeeper"), ("zagueiro", "Centre-Back"), ("lateral direito", "Right-Back"),
    ("lateral esquerdo", "Left-Back"), ("ala direito", "Right-Back"), ("ala esquerdo", "Left-Back"),
    ("volante", "Defensive Midfield"), ("meia ofensivo", "Attacking Midfield"), ("meia atacante", "Attacking Midfield"),
    ("meia direita", "Right Midfield"), ("meia esquerda", "Left Midfield"), ("meia", "Central Midfield"),
    ("meio", "Central Midfield"), ("ponta direita", "Right Winger"), ("ponta esquerda", "Left Winger"),
    ("segundo atacante", "Second Striker"), ("centroavante", "Centre-Forward"), ("atacante", "Striker"),
    ("defensor", "Defender"),
]
# grupo grosso da página do clube -> grupos de posição compatíveis (TM_GROUP)
COARSE = {"Goleiro": {"G"}, "Defensor": {"Z", "L"}, "Meia": {"V", "M", "PE", "PD"}, "Atacante": {"CA", "PE", "PD"}}
COARSE_TM = {"Goleiro": "Goalkeeper", "Defensor": "Defender", "Meia": "Midfielder", "Atacante": "Striker"}
PT_TO_EN = {norm_text(pt): en for en, (_iso, pt) in NATIONS.items()}
PT_TO_EN.update({"estados unidos": "United States", "coreia do sul": "Korea, South", "republica checa": "Czech Republic",
                 "bosnia e herzegovina": "Bosnia-Herzegovina", "costa do marfim": "Cote d'Ivoire",
                 "cabo verde": "Cape Verde", "rd congo": "DR Congo", "guine bissau": "Guinea-Bissau"})


def get(url, cache_path):
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 3000:
        return open(cache_path, encoding="utf-8", errors="replace").read()
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read().decode("utf-8", errors="replace")
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(data)
            time.sleep(1.0)
            return data
        except Exception as e:  # noqa: BLE001
            print("  erro", e, url, "tentativa", attempt, flush=True)
            time.sleep(4 + attempt * 4)
    raise SystemExit("falhou: " + url)


def text(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_team(page):
    """Nome do clube no ogol e elenco (ativos e inativos) da página do clube."""
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    name = text(title.group(1)).split(" - ")[0] if title else ""
    i = page.find('id="team_squad"')
    seg = page[i:i + 200000] if i >= 0 else ""
    stop = seg.find('<div class="section">Técnico</div>')
    if stop > 0:
        seg = seg[:stop]
    secs = [(m.start(), m.group(1)) for m in re.finditer(r'<div class="section">([^<]+)</div>', seg)]
    players = []
    for m in re.finditer(r'<div class="staff( inactive)?"><div class="number">([^<]*)</div>.*?'
                         r'<a title="([^"]*)" href="/pais/[^"]*">.*?<a href="/jogador/([^"?]+)/(\d+)[^"]*">([^<]+)</a>.*?'
                         r'<span>(\d+) anos</span>', seg, re.S):
        sec = [n for p, n in secs if p < m.start()]
        players.append({"inactive": bool(m.group(1)), "nat": htmllib.unescape(m.group(3)), "slug": m.group(4),
                        "og_id": int(m.group(5)), "name": htmllib.unescape(m.group(6)).strip(), "age": int(m.group(7)),
                        "coarse": sec[-1] if sec else None})
    return name, players


def parse_profile(page):
    """Campos da ficha do jogador (secção DADOS PESSOAIS)."""
    out = {}
    i = page.find("DADOS PESSOAIS")
    seg = page[i:i + 20000] if i >= 0 else ""
    parts = re.split(r'<div class="card-data__row[^"]*">', seg)
    for part in parts[1:]:
        lab = re.search(r'<span class="card-data__label">([^<]+)</span>', part)
        if not lab:
            continue
        vals = [text(v) for v in re.findall(r'<span class="card-data__value">(.*?)</span>(?=\s*(?:</div>|<span class="card-data__value">|$))',
                                            part, re.S)]
        vals = [v for v in vals if v] or ([text(re.sub(r'<span class="card-data__label">[^<]+</span>', "", part))])
        out[lab.group(1).strip()] = vals
    return out


def tm_position(positions, coarse):
    for p in positions or []:
        n = norm_text(p)
        for key, tm in POS_RULES:
            if n.startswith(key):
                return tm
    return COARSE_TM.get(coarse)


def match_squads(tm_players, og_players):
    """Liga cada jogador do Transfermarkt a um do ogol (primeiro os ativos). Devolve {índice TM: jogador ogol}."""
    cands = []
    for ti, p in enumerate(tm_players):
        tt = eff_tokens(p["name"])
        grp = TM_GROUP.get(p["pos"])
        for oi, o in enumerate(og_players):
            if p["age"] is None or abs(o["age"] - p["age"]) > 1:
                continue
            ns = name_sim(tt, eff_tokens(o["name"]))
            if ns < 0.55:
                continue
            compat = grp is None or o["coarse"] not in COARSE or grp in COARSE[o["coarse"]]
            score = 100 * ns + (10 if o["age"] == p["age"] else 0) + (10 if compat else -25) + (4 if not o["inactive"] else 0)
            if score >= 60:
                cands.append((score, ti, oi))
    cands.sort(reverse=True)
    used_t, used_o, pairs = set(), set(), {}
    for _score, ti, oi in cands:
        if ti in used_t or oi in used_o:
            continue
        used_t.add(ti)
        used_o.add(oi)
        pairs[ti] = og_players[oi]
    return pairs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--tm", required=True, help="json de fetch_transfermarkt.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--today", default=None, help="AAAA-MM-DD (idade dos jogadores novos)")
    ap.add_argument("--only", help="só este clube (nome no config)")
    args = ap.parse_args()
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    cfg = json.load(open(args.config, encoding="utf-8"))
    clubs_cfg = {w["tm_id"]: w for lg in cfg["leagues"] for w in lg.get("clubs", [])}
    tm = json.load(open(args.tm, encoding="utf-8"))
    os.makedirs(os.path.join(args.cache_dir, "teams"), exist_ok=True)
    os.makedirs(os.path.join(args.cache_dir, "players"), exist_ok=True)

    totals = collections.Counter()
    unknown_nats = collections.Counter()
    for c in tm:
        w = clubs_cfg.get(c["id"])
        if not w or not w.get("ogol") or (args.only and w["name"] != args.only):
            continue
        slug_, oid = w["ogol"].split("/")
        page = get(f"{BASE}/equipe/{slug_}/{oid}", os.path.join(args.cache_dir, "teams", f"{oid}.html"))
        og_name, og_players = parse_team(page)
        active = [o for o in og_players if not o["inactive"]]
        inactive = [o for o in og_players if o["inactive"]]
        pairs = match_squads(c["players"], active)
        rest = [i for i in range(len(c["players"])) if i not in pairs]
        pairs_in = match_squads([c["players"][i] for i in rest], inactive)
        gone = {rest[k] for k in pairs_in}
        kept = [p for i, p in enumerate(c["players"]) if i not in gone]
        matched_og = {o["og_id"] for o in pairs.values()}
        added, rejected = [], []
        for o in active:
            if o["og_id"] in matched_og:
                continue
            prof = parse_profile(get(f"{BASE}/jogador/{o['slug']}/{o['og_id']}",
                                     os.path.join(args.cache_dir, "players", f"{o['og_id']}.html")))
            club_now = (prof.get("Clube atual") or [""])[0]
            if norm_text(club_now.split("(")[0]) != norm_text(og_name):
                rejected.append((o["name"], club_now))
                continue
            dob = re.search(r"(\d{4})-(\d{2})-(\d{2})", (prof.get("Data de Nascimento") or [""])[0])
            if dob:
                y, mo, d = map(int, dob.groups())
                age = today.year - y - ((today.month, today.day) < (mo, d))
                dob_s = f"{y:04d}-{mo:02d}-{d:02d}"
            else:
                age, dob_s = o["age"], None
            nats = []
            for n in prof.get("Nacionalidade") or [o["nat"]]:
                en = PT_TO_EN.get(norm_text(n))
                if en:
                    nats.append(en)
                else:
                    unknown_nats[n] += 1
            added.append({"tm_id": f"og{o['og_id']}", "slug": o["slug"], "name": o["name"], "num": "",
                          "pos": tm_position(prof.get("Posição"), o["coarse"]), "dob": dob_s, "age": age, "nats": nats,
                          "height": "", "foot": "", "joined": "", "signed_from": None, "contract": "", "value": None,
                          "on_loan_from": None, "source": "ogol"})
        dropped = [c["players"][i]["name"] for i in sorted(gone)]
        n_tm = len(c["players"])
        c["players"] = kept + added
        c["ogol"] = {"path": w["ogol"], "name": og_name, "squad": len(og_players), "active": len(active),
                     "dropped_inactive": dropped, "added": [a["name"] for a in added], "rejected": rejected}
        totals["tm"] += n_tm
        totals["dropped"] += len(gone)
        totals["added"] += len(added)
        totals["rejected"] += len(rejected)
        print(f"{w['name']:22} TM={n_tm:2} saem={len(gone):2} ogol ativos={len(active):2} "
              f"entram={len(added):2} recusados={len(rejected):2} -> {len(c['players']):2}", flush=True)
    # um jogador que a ficha do ogol põe neste clube não pode estar também noutro clube da liga (ex.: o Transfermarkt
    # ainda o tem no clube antigo): sai de lá se a data de nascimento é a mesma e o nome é parecido
    moved = []
    for c in tm:
        for a in [p for p in c["players"] if p.get("source") == "ogol" and p["dob"]]:
            for c2 in tm:
                if c2 is c:
                    continue
                for p in list(c2["players"]):
                    if p.get("source") != "ogol" and p["dob"] == a["dob"]                             and name_sim(eff_tokens(p["name"]), eff_tokens(a["name"])) >= 0.55:
                        c2["players"].remove(p)
                        moved.append((p["name"], c2["name"], c["name"]))
    if moved:
        print(f"{len(moved)} jogadores tirados de um clube porque a ficha do ogol os põe noutro:", moved[:12])
    json.dump(tm, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print("totais:", dict(totals), "| nacionalidades sem tradução:", dict(unknown_nats))
    print("jogadores no ficheiro:", sum(len(c["players"]) for c in tm))


if __name__ == "__main__":
    sys.exit(main())
