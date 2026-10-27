"""Gera frontend/elo_sim.json: Elo simulado dos clubes de um patch com jogadores (formato teams.json/players.json).

Uso:
    python tools/build_elo_sim.py --legacy "…/temporada_2026_brasil_abc_12_paises_…" --patch-pt "…/portugal_2026"

Ideia: os clubes portugueses têm um Elo de referência (já trabalhado) e, neste patch, têm jogadores. Mede-se a
força de cada clube (média do OVER dos 14 melhores jogadores), ajusta-se uma reta  Elo = a + b * força  nos
clubes portugueses e aplica-se aos restantes. Portugal fica de fora do resultado (já está configurado).

Referência dos portugueses:
    ClubElo real (frontend/elo.json, clubes com fonte "clubelo"), se houver 6 ou mais ligações -> escala "clubelo"
    senão o campo elo do patch portugal_2026 (0 a 1000)                                          -> escala "jogo"
"""
import argparse
import collections
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
from build_elo import chave  # noqa: E402

TOP = 14


def ler(p):
    return json.load(open(p, encoding="utf-8"))


def reta(pontos):
    xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    a = my - b * mx
    res = [y - (a + b * x) for x, y in pontos]
    return a, b, (statistics.pstdev(res) if len(res) > 1 else 0), len(pontos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", required=True)
    ap.add_argument("--patch-pt", required=True)
    ap.add_argument("--elo", default=os.path.join(os.path.dirname(__file__), "..", "frontend", "elo.json"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "frontend", "elo_sim.json"))
    a = ap.parse_args()

    teams = ler(os.path.join(a.legacy, "data", "teams.json"))["teams"]
    jogadores = collections.defaultdict(list)
    for p in ler(os.path.join(a.legacy, "data", "players.json"))["players"]:
        if p.get("OVER"):
            jogadores[p["team_id"]].append(p["OVER"])
    forca = {t["id"]: statistics.mean(sorted(jogadores[t["id"]], reverse=True)[:TOP]) for t in teams if jogadores[t["id"]]}

    # referência dos portugueses
    pt_dir = os.path.join(a.patch_pt, "data", "clubs")
    pt, pt_exato = {}, {}
    for f in os.listdir(pt_dir):
        d = ler(os.path.join(pt_dir, f))
        pt[chave(d["nome"])] = d
        pt_exato[chave(d["nome"], ruido=False)] = d
    elo = ler(a.elo)["clubes"] if os.path.exists(a.elo) else {}
    anc_real, anc_jogo, sem = [], [], []
    for t in teams:
        if t["country_id"] != "portugal" or t["id"] not in forca:
            continue
        k = chave(t["nome"])
        d = pt_exato.get(chave(t["nome"], ruido=False)) or pt.get(k) or next((v for kk, v in pt.items() if kk.startswith(k) or k.startswith(kk)), None)
        if not d:
            sem.append(t["nome"])
            continue
        anc_jogo.append((forca[t["id"]], d["elo"]))
        e = elo.get(d["id"])
        if e and e["fonte"] == "clubelo":
            anc_real.append((forca[t["id"]], e["elo"]))
    if len(anc_real) >= 6:
        escala, anc = "clubelo", anc_real
    else:
        escala, anc = "jogo", anc_jogo
    if len(anc) < 6:
        sys.exit(f"só {len(anc)} clubes portugueses ligados; faltam referências ({sem})")
    ka, kb, sd, n = reta(anc)

    out = {"meta": {"escala": escala, "ancoras": n, "a": round(ka, 2), "b": round(kb, 2), "desvio": round(sd, 1),
                    "top": TOP, "ref_pt": "ClubElo" if escala == "clubelo" else "elo do patch portugal_2026"},
           "clubes": {}}
    for t in teams:
        if t["country_id"] == "portugal" or t["id"] not in forca:
            continue
        v = ka + kb * forca[t["id"]]
        if escala == "jogo":
            v = min(max(v, 0), 1000)
        out["clubes"][t["id"]] = {"elo": round(v), "fonte": "simulado", "forca": round(forca[t["id"]], 1), "elo_atual": t["elo"]}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{len(out['clubes'])} clubes simulados (escala {escala}) -> {os.path.abspath(a.out)}")
    print("reta:", out["meta"])
    if sem:
        print("portugueses sem referência:", sem)
    top = sorted(out["clubes"].items(), key=lambda kv: -kv[1]["elo"])
    nome = {t["id"]: t["nome"] for t in teams}
    for i, c in top[:8] + top[-5:]:
        print(f"  {nome[i]:28} força {c['forca']:5}  elo simulado {c['elo']}  (atual {c['elo_atual']})")


if __name__ == "__main__":
    main()
