"""Descarrega os ratings oficiais da EA SPORTS FC (todos os jogadores masculinos) para um .json.

A API pública da página de ratings da EA não precisa de chave. Devolve no máximo 100 jogadores por pedido
(~16 mil jogadores, ~165 pedidos, 1-2 minutos). Guarda só os campos usados pelo build_leagues.py.

Uso:
    python tools/fetch_ea.py --out tools/work/ea_all.json
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
URL = "https://drop-api.ea.com/rating/ea-sports-fc?locale=en&gender=0&limit=100&offset=%d"


def fetch_page(offset):
    for attempt in range(5):
        try:
            req = urllib.request.Request(URL % offset, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print("  nova tentativa", offset, attempt, e, flush=True)
            time.sleep(2 + attempt * 2)
    raise SystemExit("falhou no offset %d" % offset)


def compact(it):
    stats = {k: v["value"] for k, v in (it.get("stats") or {}).items()}
    return {
        "id": it["id"], "ovr": it["overallRating"], "rank": it.get("rank"),
        "first": it.get("firstName"), "last": it.get("lastName"), "common": it.get("commonName"),
        "birth": it.get("birthdate"), "height": it.get("height"), "weight": it.get("weight"),
        "foot": it.get("preferredFoot"), "sm": it.get("skillMoves"), "wf": it.get("weakFootAbility"),
        "nat": (it.get("nationality") or {}).get("label"), "natid": (it.get("nationality") or {}).get("id"),
        "team": (it.get("team") or {}).get("label"), "teamid": (it.get("team") or {}).get("id"),
        "league": it.get("leagueName"),
        "pos": (it.get("position") or {}).get("shortLabel"),
        "alt": [a.get("shortLabel") for a in (it.get("alternatePositions") or [])],
        "stats": stats,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="ficheiro .json de saída")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    players, offset, total = [], 0, None
    while True:
        d = fetch_page(offset)
        total = d.get("totalItems", total)
        items = d.get("items", [])
        players += [compact(it) for it in items]
        offset += 100
        if offset % 2000 == 0:
            print(f"{len(players)} / {total}", flush=True)
        if not items or offset >= (total or 0):
            break
        time.sleep(0.25)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(players, f, ensure_ascii=False)
    print(f"{len(players)} jogadores guardados em {args.out}")


if __name__ == "__main__":
    sys.exit(main())
