"""Gera frontend/elo.json: o Elo (escala ClubElo) de cada clube de um patch do GoFoot.

Uso:
    python tools/build_elo.py --ranking ranking.csv --patch "C:/Users/User/Documents/Gofoot/Patches/portugal_2026"

O ranking é o CSV do ClubElo (http://api.clubelo.com/AAAA-MM-DD, colunas Rank,Club,Country,Level,Elo,From,To)
ou qualquer CSV com as colunas Club e Elo. O patch só é lido, nunca alterado.

Clubes que aparecem no ranking ficam com o Elo real. Os restantes recebem uma estimativa (ver wiki):
    base da divisão  = média do Elo real dos clubes dessa divisão (se houver 2+), senão extrapola
                       a partir da divisão mais próxima com dados, descontando o degrau médio entre divisões
    estimativa       = base + k * (reputação - reputação média da divisão), limitada a ±LIMITE da base
"""
import argparse
import csv
import difflib
import glob
import io
import json
import os
import re
import statistics
import sys
import unicodedata
from datetime import date

LIMITE = 120          # máximo que uma estimativa se afasta da base da divisão
DEGRAU_PADRAO = 80    # Elo entre divisões consecutivas quando não há dados para o medir
K_PADRAO = 3.0        # Elo por ponto de reputação quando não há dados para o medir
RUIDO = {"fc", "sc", "cd", "cf", "sl", "sad", "clube", "club", "futebol", "desportivo", "de", "do", "da", "dos",
         "das", "e", "associacao", "academica", "sport", "grupo", "gd", "ad", "ud", "cs", "sporting", "atletico"}
# nomes do ClubElo que o normalizador não resolve sozinho (chave: nome normalizado do ClubElo)
ALIAS = {
    "sporting": "pt_sporting", "porto": "pt_fcporto", "benfica": "pt_benfica", "braga": "pt_scbraga",
    "guimaraes": "pt_vitoriasc", "vitoria guimaraes": "pt_vitoriasc", "academica": "pt_academica",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).split()


def chave(s, ruido=True):
    toks = [t for t in norm(s) if not (ruido and t in RUIDO)]
    return " ".join(toks) or " ".join(norm(s))


def ler_ranking(path):
    raw = open(path, "rb").read().decode("utf-8-sig", errors="replace")
    delim = "\t" if raw.count("\t") > raw.count(",") else ","
    rows = list(csv.DictReader(io.StringIO(raw), delimiter=delim))
    if not rows:
        sys.exit("ranking vazio")
    cols = {k.strip().lower(): k for k in rows[0]}
    if "club" not in cols or "elo" not in cols:
        sys.exit(f"o ranking precisa das colunas Club e Elo (tem: {list(cols)})")
    out = []
    for r in rows:
        try:
            out.append({"club": r[cols["club"]].strip(), "elo": float(r[cols["elo"]]),
                        "country": (r.get(cols.get("country", ""), "") or "").strip()})
        except (ValueError, TypeError):
            continue
    # se houver coluna Country, fica só Portugal; senão assume que o ficheiro já é só dele
    if any(o["country"] for o in out):
        out = [o for o in out if o["country"].upper() in ("POR", "PRT")]
    return out


def ler_patch(patch):
    comps = json.load(open(os.path.join(patch, "data", "competitions.json"), encoding="utf-8"))["competitions"]
    nivel = {}
    for c in comps:
        if c.get("division_level"):
            for t in c.get("teams", []):
                nivel[t] = c["division_level"]
    clubes = []
    for f in sorted(glob.glob(os.path.join(patch, "data", "clubs", "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        clubes.append({"id": d["id"], "nome": d["nome"], "rep": d.get("reputacao", 0), "nivel": nivel.get(d["id"], 0)})
    return clubes


def casar(clubes, ranking):
    """Liga cada clube do patch a uma linha do ranking. Devolve {id: linha} e a lista de ligações duvidosas."""
    por_chave = {}
    for r in ranking:
        por_chave.setdefault(chave(r["club"]), r)
        por_chave.setdefault(chave(r["club"], ruido=False), r)
    usados, res, duvidosas = set(), {}, []
    for c in clubes:
        k1, k2 = chave(c["nome"]), chave(c["nome"], ruido=False)
        alvo = None
        for r in ranking:
            if ALIAS.get(chave(r["club"], ruido=False)) == c["id"]:
                alvo = r
        alvo = alvo or por_chave.get(k1) or por_chave.get(k2)
        if alvo is None:
            melhor = difflib.get_close_matches(k1, list(por_chave), n=1, cutoff=0.88)
            if melhor:
                alvo = por_chave[melhor[0]]
                duvidosas.append((c["nome"], alvo["club"]))
        if alvo is not None and alvo["club"] not in usados:
            usados.add(alvo["club"])
            res[c["id"]] = alvo
    return res, duvidosas


def estimar(clubes, reais):
    por_nivel = {}
    for c in clubes:
        por_nivel.setdefault(c["nivel"], []).append(c)
    base = {n: statistics.mean(reais[c["id"]] for c in cs if c["id"] in reais)
            for n, cs in por_nivel.items() if sum(c["id"] in reais for c in cs) >= 2}
    niveis = sorted(por_nivel)
    degraus = [(base[a] - base[b]) / (b - a) for a in base for b in base if b > a]
    degrau = max(statistics.mean(degraus), 20) if degraus else DEGRAU_PADRAO
    for n in niveis:
        if n not in base and base:
            perto = min(base, key=lambda m: abs(m - n))
            base[n] = base[perto] - degrau * (n - perto)
    # k: declive Elo/reputação dentro das divisões, só com clubes de Elo real
    xs, ys = [], []
    for n, cs in por_nivel.items():
        rs = [c for c in cs if c["id"] in reais]
        if len(rs) >= 3:
            mr, me = statistics.mean(c["rep"] for c in rs), statistics.mean(reais[c["id"]] for c in rs)
            xs += [c["rep"] - mr for c in rs]
            ys += [reais[c["id"]] - me for c in rs]
    sxx = sum(x * x for x in xs)
    k = min(max(sum(x * y for x, y in zip(xs, ys)) / sxx, 0.5), 6.0) if sxx else K_PADAO
    est = {}
    for n, cs in por_nivel.items():
        mrep = statistics.mean(c["rep"] for c in cs)
        for c in cs:
            if c["id"] not in reais:
                v = base[n] + k * (c["rep"] - mrep)
                est[c["id"]] = round(min(max(v, base[n] - LIMITE), base[n] + LIMITE))
    return est, {"base": {str(n): round(v) for n, v in sorted(base.items())}, "degrau": round(degrau), "k": round(k, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranking", required=True)
    ap.add_argument("--patch", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "frontend", "elo.json"))
    a = ap.parse_args()
    clubes, ranking = ler_patch(a.patch), ler_ranking(a.ranking)
    ligados, duvidosas = casar(clubes, ranking)
    reais = {i: r["elo"] for i, r in ligados.items()}
    if not reais:
        sys.exit("nenhum clube do patch foi encontrado no ranking")
    est, params = estimar(clubes, reais)
    out = {"meta": {"gerado": date.today().isoformat(), "fonte": "clubelo.com", "reais": len(reais),
                    "estimados": len(est), **params}, "clubes": {}}
    for c in clubes:
        if c["id"] in reais:
            out["clubes"][c["id"]] = {"elo": round(reais[c["id"]]), "fonte": "clubelo", "ref": ligados[c["id"]]["club"]}
        else:
            out["clubes"][c["id"]] = {"elo": est[c["id"]], "fonte": "estimado"}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{len(reais)} reais, {len(est)} estimados -> {os.path.abspath(a.out)}")
    print("parâmetros:", params)
    for nome, ref in duvidosas:
        print(f"  ligação aproximada (confirmar): {nome} = {ref}")
    for c in clubes:
        if c["id"] in reais:
            print(f"  {c['nome']:32} <- {ligados[c['id']]['club']}")


if __name__ == "__main__":
    main()
