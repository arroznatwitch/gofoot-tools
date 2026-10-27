"""Escreve uma cópia do teams.json do patch antigo com o campo elo (Elo do jogo) atualizado.

Uso:
    python tools/export_elo_jogo.py --legacy "…/temporada_2026_…" --patch-pt "…/portugal_2026" --out saida_elo

- clubes não portugueses: elo = Elo simulado (frontend/elo_sim.json), calibrado nos clubes portugueses
- clubes portugueses: elo = o do patch portugal_2026 (a referência da calibração)
O patch original não é tocado: sai uma cópia em --out (teams.json e elo_jogo.csv).
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from build_elo import chave  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", required=True)
    ap.add_argument("--patch-pt", required=True)
    ap.add_argument("--sim", default=os.path.join(os.path.dirname(__file__), "..", "frontend", "elo_sim.json"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sim = json.load(open(a.sim, encoding="utf-8"))
    if sim["meta"]["escala"] != "jogo":
        sys.exit("o elo_sim.json está na escala ClubElo; este export só atualiza o Elo do jogo (0 a 1000)")
    teams = json.load(open(os.path.join(a.legacy, "data", "teams.json"), encoding="utf-8"))
    pt = {}
    for f in os.listdir(os.path.join(a.patch_pt, "data", "clubs")):
        d = json.load(open(os.path.join(a.patch_pt, "data", "clubs", f), encoding="utf-8"))
        pt[chave(d["nome"])] = d["elo"]
    ligas = {}
    for l in json.load(open(os.path.join(a.legacy, "data", "leagues.json"), encoding="utf-8"))["leagues"]:
        ligas[l["id"]] = l
    liga_de = {}
    for m in json.load(open(os.path.join(a.legacy, "data", "league_teams.json"), encoding="utf-8"))["initial_mappings"]:
        if ligas.get(m["league_id"], {}).get("division_level"):
            for t in m["teams"]:
                liga_de[t] = ligas[m["league_id"]]["name"]
    os.makedirs(a.out, exist_ok=True)
    linhas, igual = [], 0
    for t in teams["teams"]:
        antigo = t["elo"]
        if t["country_id"] == "portugal":
            k = chave(t["nome"])
            novo = pt.get(k) or next((v for kk, v in pt.items() if kk.startswith(k) or k.startswith(kk)), None)
        else:
            novo = sim["clubes"].get(t["id"], {}).get("elo")
        if novo is None:
            igual += 1
            continue
        t["elo"] = float(novo)
        linhas.append([t["id"], t["nome"], t["country_id"], liga_de.get(t["id"], ""), antigo, novo])
    with open(os.path.join(a.out, "teams.json"), "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(teams, ensure_ascii=False, indent=2).replace("\n", "\r\n"))
    with open(os.path.join(a.out, "elo_jogo.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "clube", "pais", "liga", "elo_antigo", "elo_novo"])
        w.writerows(sorted(linhas, key=lambda r: (r[2], r[3], -r[5])))
    print(f"{len(linhas)} clubes atualizados, {igual} sem alteração -> {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
