"""Tira as cópias de jogadores que estão num clube onde o Transfermarkt diz que eles não jogam.

Caso que levou a isto: o IFK Göteborg tinha 21 jogadores do IF Elfsborg e o Ypiranga-RS (ou o Inter de Limeira) a mesma coisa:
duas linhas da mesma pessoa em clubes diferentes, com os mesmos valores. O plantel atual do Transfermarkt diz qual dos dois clubes
é o certo. Para cada clube indicado em --squad, uma linha desse clube que não está no plantel do Transfermarkt e que tem uma
cópia (mesmo nome, nacionalidade parecida, idade com 1 ano de diferença) noutro clube sai; a cópia fica. Se a linha tem dados do
FM (Best Rating) fica sem OVER nem atributos; se não, apaga-se.

Uso:
    python tools/dedupe_by_squad.py --csv tools/work/players_dedupe.csv --out tools/work/players_dedupe2.csv \\
        --report tools/work/duplicados_por_plantel.csv --cache-dir tools/work/tm_dedupe \\
        --squad "Ifk Goteborg=<id do Transfermarkt>:<slug>" --squad "Ypiranga-RS=..."
"""
import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_transfermarkt as F  # noqa: E402
import gofoot_formulas as G  # noqa: E402
from common import CI, COLS, eff_tokens, name_sim, slug, split_raw, tokens, unquote  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
GOFOOT_COLS = ["Pe", "Posicao", "TAL", "Valor", "TEC", "ATA", "DEF", "FIS", "MEN", "REF", "POS_GK", "AER", "SAI", "OVER", "Salario"]
COLUMN = {"TEC": "TEC", "ATA": "ATA", "DEF": "DEF", "FIS": "FIS", "MEN": "MEN", "REF": "REF", "POS": "POS_GK", "AER": "AER", "SAI": "SAI"}


def nat_set(s):
    return {x.strip().lower() for x in (s or "").split("/") if x.strip()}


def current_squad(club_id, club_slug, cache_dir, season=2026):
    """Plantel atual no Transfermarkt (a época certa de cada clube: ver fetch_transfermarkt.py)."""
    sid = season
    for _ in range(2):
        page = F.get(f"https://www.transfermarkt.com/{club_slug}/kader/verein/{club_id}/saison_id/{sid}/plus/1",
                     os.path.join(cache_dir, f"squad_{club_id}_{sid}.html"))
        label = F.season_label(page)
        if label and re.fullmatch(r"\d{4}", label) and int(label) > season:
            sid = season - 1
            continue
        return F.parse_squad(page), label
    return F.parse_squad(page), label


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--squad", action="append", required=True, metavar="CLUBE_NO_CSV=ID:SLUG")
    args = ap.parse_args()
    os.makedirs(args.cache_dir, exist_ok=True)

    squads = {}
    for item in args.squad:
        club, _, rest = item.rpartition("=")
        cid, _, sl = rest.partition(":")
        players, label = current_squad(int(cid), sl, args.cache_dir)
        squads[slug(club)] = (club, players)
        print(f"{club}: {len(players)} jogadores no Transfermarkt (época {label})")

    raw = open(args.csv, "rb").read().decode("latin-1")
    ends_nl = raw.endswith("\r\n")
    lines = raw.split("\r\n")
    if ends_nl:
        lines.pop()
    assert split_raw(lines[0]) == COLS
    rows = []
    for i, line in enumerate(lines[1:], start=1):
        f = [unquote(x) for x in split_raw(line)]
        if not f[CI["OVER"]].strip():
            continue
        grp = G.posicao_grupo(f[CI["Posicao"]] or f[CI["Position"]])
        if not grp:
            continue
        at = {k: (int(f[CI[c]]) if f[CI[c]].strip().lstrip("-").isdigit() else None) for k, c in COLUMN.items() if k in G.attr_keys(grp)}
        if G.calcular_over(grp, at) is None:
            continue
        club = f[CI["Club"]]
        rows.append({"line": i, "f": f, "name": f[CI["Name"]], "key": " ".join(sorted(tokens(f[CI["Name"]]))), "club": club,
                     "cs": slug(club) if club not in ("", "-") else "", "nat": f[CI["Nation"]], "over": f[CI["OVER"]],
                     "has_fm": bool(f[CI["Best Rating"]].strip()),
                     "age": int(f[CI["Age"]]) if f[CI["Age"]].strip().lstrip("-").isdigit() else None})
    by_key, by_line = {}, {r["line"]: r for r in rows}
    for r in rows:
        by_key.setdefault(r["key"], []).append(r)

    def in_squad(r, players):
        toks = eff_tokens(r["name"])
        return any((p["age"] is None or r["age"] is None or abs(p["age"] - r["age"]) <= 2) and name_sim(toks, eff_tokens(p["name"])) >= 0.8
                   for p in players)

    removed = {}
    for r in rows:
        if r["cs"] not in squads or in_squad(r, squads[r["cs"]][1]):
            continue
        twins = [s for s in by_key[r["key"]] if s["line"] != r["line"] and s["cs"] != r["cs"] and s["line"] not in removed
                 and r["age"] is not None and s["age"] is not None and abs(r["age"] - s["age"]) <= 1
                 and (not r["nat"] or not s["nat"] or nat_set(r["nat"]) & nat_set(s["nat"]) or r["over"] == s["over"])]
        if twins:
            removed[r["line"]] = twins[0]

    with open(args.report, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["acao", "nome", "clube (sai)", "idade", "OVER", "->", "mantido: nome", "mantido: clube", "mantido: idade", "mantido: OVER"])
        for ln, s in sorted(removed.items(), key=lambda kv: by_line[kv[0]]["club"]):
            r = by_line[ln]
            w.writerow(["tirar OVER" if r["has_fm"] else "apagar linha", r["name"], r["club"], r["age"], r["over"], "->", s["name"], s["club"], s["age"], s["over"]])
    per_club = {}
    for ln in removed:
        per_club[by_line[ln]["club"]] = per_club.get(by_line[ln]["club"], 0) + 1
    print("linhas a tirar por clube:", per_club, "| relatório:", args.report)

    out = [lines[0]]
    for i, line in enumerate(lines[1:], start=1):
        if i not in removed:
            out.append(line)
            continue
        if not by_line[i]["has_fm"]:
            continue
        f = split_raw(line)
        for c in GOFOOT_COLS:
            f[CI[c]] = ""
        out.append(";".join(f))
    open(args.out, "wb").write(("\r\n".join(out) + ("\r\n" if ends_nl else "")).encode("latin-1"))
    print("escrito:", args.out)


if __name__ == "__main__":
    sys.exit(main())
