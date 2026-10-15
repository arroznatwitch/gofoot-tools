"""Procura (e tira) jogadores duplicados entre os que aparecem no site (linhas com OVER e atributos completos).

Dois tipos de duplicado, os dois já existiam nos dados antigos:
  * a mesma pessoa duas vezes (o nome só muda na grafia: "Aleix García" e "García, Aleix", "Néné" e "Nene");
  * homónimos que herdaram o mesmo OVER (o OVER foi copiado para todas as linhas do FM com o mesmo nome, como os dois
    Gabriel Barbosa e os dois Rony do Santos).

Só se mexe em casos claros (ver CLASSES); o resto vai para o relatório. Linha que sai: se tem dados do FM (Best Rating) fica no
CSV sem OVER nem atributos (o site deixa de a mostrar); se foi escrita à mão ou acrescentada por um build e não tem dados do FM,
apaga-se. Nunca se mexe nos OVER das linhas que ficam.

Uso:
    python tools/dedupe_players.py --csv players.csv --report tools/work/duplicados.csv            (só relatório)
    python tools/dedupe_players.py --csv players.csv --report tools/work/duplicados.csv --out tools/work/players_dedupe.csv
"""
import argparse
import collections
import csv
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gofoot_formulas as G  # noqa: E402
from common import CI, COLS, load_leagues_js, slug, split_raw, tokens, unquote  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
REPO = os.path.abspath(os.path.join(HERE, ".."))
GOFOOT_COLS = ["Pe", "Posicao", "TAL", "Valor", "TEC", "ATA", "DEF", "FIS", "MEN", "REF", "POS_GK", "AER", "SAI", "OVER", "Salario"]
COLUMN = {"TEC": "TEC", "ATA": "ATA", "DEF": "DEF", "FIS": "FIS", "MEN": "MEN", "REF": "REF", "POS": "POS_GK", "AER": "AER", "SAI": "SAI"}


def rated_ids(rev):
    """Ids com OVER no players.csv de um commit (git show)."""
    res = subprocess.run(["git", "-C", REPO, "show", f"{rev}:players.csv"], capture_output=True)
    if res.returncode != 0:
        raise SystemExit(f"não consegui ler o players.csv de {rev} no git")
    out = set()
    for ln in res.stdout.decode("latin-1").replace("\r\n", "\n").split("\n")[1:]:
        if ln:
            f = split_raw(ln)
            if unquote(f[CI["OVER"]]).strip():
                out.add(unquote(f[CI["Id"]]))
    return out


def nat_set(s):
    return {x.strip().lower() for x in (s or "").split("/") if x.strip()}


def load(path):
    raw = open(path, "rb").read().decode("latin-1")
    ends_nl = raw.endswith("\r\n")
    lines = raw.split("\r\n")
    if ends_nl:
        lines.pop()
    assert split_raw(lines[0]) == COLS, "cabeçalho inesperado"
    return lines, ends_nl


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--report", required=True, help="CSV com todos os duplicados encontrados e o que se faz a cada um")
    ap.add_argument("--out", help="players.csv sem os duplicados claros (sem isto só escreve o relatório)")
    ap.add_argument("--leagues-js", default=os.path.join(HERE, "..", "frontend", "leagues.js"))
    args = ap.parse_args()

    human = rated_ids("855cdaa^")  # linhas feitas pelo utilizador, antes de a geração por FM
    antes_builds = rated_ids("732d21d^")  # tudo o que já existia antes dos builds das ligas novas
    site = {slug(c) for ls in load_leagues_js(args.leagues_js).values() for cl in ls.values() for c in cl}

    lines, ends_nl = load(args.csv)
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
            continue  # incompleto: o site não o mostra
        club = f[CI["Club"]]
        ident = f[CI["Id"]]
        rows.append({
            "line": i, "f": f, "id": ident, "name": f[CI["Name"]], "key": " ".join(sorted(tokens(f[CI["Name"]]))),
            "club": club, "cs": slug(club) if club not in ("", "-") else "", "nat": f[CI["Nation"]], "grp": grp,
            "over": int(f[CI["OVER"]]), "tal": f[CI["TAL"]], "has_fm": bool(f[CI["Best Rating"]].strip()),
            "rating": float(f[CI["Best Rating"]].split("%")[0]) if f[CI["Best Rating"]].strip() and f[CI["Best Rating"]].split("%")[0].replace(".", "").isdigit() else 0.0,
            "age": int(f[CI["Age"]]) if f[CI["Age"]].strip().lstrip("-").isdigit() else None,
            "origin": "human" if ident in human else ("fm_pass" if ident in antes_builds else "mine"),
        })

    # clubes com sigla de 3 letras que não estão em nenhuma liga (Fortaleza = "For"): vêm de exportações do jogo
    by_club = collections.defaultdict(list)
    for r in rows:
        by_club[r["cs"]].append(r)
    code_of = {}
    for cs, rs in by_club.items():
        if cs and len(cs) <= 3 and cs not in site:
            names = {r["key"] for r in rs}
            best = max(((len(names & {x["key"] for x in other}), other_cs) for other_cs, other in by_club.items()
                        if other_cs != cs and other_cs in site), default=(0, None))
            if best[0] >= 8:
                code_of[cs] = best[1]

    def same_values(x, y):
        return x["over"] == y["over"] and x["tal"] == y["tal"]

    def age_diff(x, y):
        return abs(x["age"] - y["age"]) if x["age"] is not None and y["age"] is not None else 99

    # ------------------------------------------------------------------------------------------ pares
    def classify(x, y):
        ox = {x["origin"], y["origin"]}
        d = age_diff(x, y)
        nat_ok = not x["nat"] or not y["nat"] or bool(nat_set(x["nat"]) & nat_set(y["nat"]))
        if x["cs"] and x["cs"] == y["cs"]:  # o mesmo clube
            if "mine" in ox:  # um build criou uma segunda linha da mesma pessoa
                return "mesma pessoa (duplicada num build)" if d <= 1 and nat_ok and "fm_pass" not in ox else None
            if ox == {"human", "fm_pass"}:  # o FM e o utilizador escrevem a nacionalidade de formas diferentes (Eritreia / Suécia)
                return "mesma pessoa (grafia diferente)" if d <= 2 else None
            if ox == {"fm_pass"}:
                return "mesma pessoa (grafia diferente)" if d <= 1 and nat_ok else None
            if same_values(x, y):  # as duas humanas
                return "homónimos com o mesmo OVER" if d > 1 else "mesma pessoa, linha humana repetida"
            return "ambíguo: duas linhas humanas, valores diferentes" if d <= 1 and nat_ok else None
        cx, cy = code_of.get(x["cs"], x["cs"]), code_of.get(y["cs"], y["cs"])
        if x["cs"] != y["cs"] and cx == cy and (x["cs"] in code_of or y["cs"] in code_of):
            return "cópia com sigla do clube (For, Spt, Cri)" if same_values(x, y) and d <= 1 else None
        if x["cs"] and y["cs"] and len(x["key"].split()) >= 2 and d <= 1 and nat_ok:  # clubes diferentes, nome completo
            if ox == {"human", "fm_pass"}:
                return "o FM tem-no noutro clube (linha antiga do FM)"
            if ox == {"human"}:
                return "em dois clubes com os mesmos valores" if same_values(x, y) else "ambíguo: duas linhas humanas em clubes diferentes"
            if ox == {"human", "mine"}:
                return "em dois clubes (build + linha humana)"
        return None

    by_key = collections.defaultdict(list)
    for r in rows:
        by_key[r["key"]].append(r)
    pairs = []  # (classe, x, y)
    for v in by_key.values():
        for a_ in range(len(v)):
            for b_ in range(a_ + 1, len(v)):
                cls = classify(v[a_], v[b_])
                if cls:
                    pairs.append((cls, v[a_], v[b_]))

    # ------------------------------------------------------------------------------------------ o que se faz
    AUTO = {"mesma pessoa (duplicada num build)", "mesma pessoa (grafia diferente)", "mesma pessoa, linha humana repetida",
            "homónimos com o mesmo OVER", "cópia com sigla do clube (For, Spt, Cri)", "o FM tem-no noutro clube (linha antiga do FM)"}
    origin_rank = {"human": 0, "mine": 1, "fm_pass": 2}

    def keeper(x, y, cls):
        if cls == "cópia com sigla do clube (For, Spt, Cri)":
            return (y, x) if x["cs"] in code_of else (x, y)
        if cls in ("homónimos com o mesmo OVER", "mesma pessoa, linha humana repetida"):  # fica o que tem o rating do FM mais alto
            order = sorted((x, y), key=lambda r: (-r["rating"], not r["has_fm"], r["line"]))
        else:
            order = sorted((x, y), key=lambda r: (origin_rank[r["origin"]], not r["has_fm"], -r["rating"], r["line"]))
        return order[0], order[1]

    removed = {}  # line -> (classe, mantido)
    for cls, x, y in pairs:
        if cls not in AUTO:
            continue
        keep, drop = keeper(x, y, cls)
        if drop["line"] in removed or drop["line"] == keep["line"]:
            continue
        removed[drop["line"]] = (cls, keep)
    # uma linha que fica não pode estar também a sair (cadeias): resolve-se mantendo a primeira decisão
    still = {ln for ln in removed}
    for ln, (cls, keep) in list(removed.items()):
        if keep["line"] in still:  # o que ia ficar sai por outro par: usa o que o substitui
            k2 = removed[keep["line"]][1]
            removed[ln] = (cls, k2)

    # ------------------------------------------------------------------------------------------ relatório
    by_line = {r["line"]: r for r in rows}
    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    with open(args.report, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["classe", "acao", "nome", "clube", "idade", "pos", "OVER", "TAL", "origem", "rating FM", "Id", "->", "mantido: nome",
                    "mantido: clube", "mantido: idade", "mantido: OVER", "mantido: TAL", "mantido: Id"])
        for cls, x, y in sorted(pairs, key=lambda p: (p[0], p[1]["club"], p[1]["name"])):
            if cls in AUTO:
                keep, drop = keeper(x, y, cls)
                acao = ("apagar linha" if not drop["has_fm"] else "tirar OVER") if drop["line"] in removed else "(já tratado)"
            else:
                keep, drop, acao = x, y, "só relatório"
            w.writerow([cls, acao, drop["name"], drop["club"], drop["age"], drop["grp"], drop["over"], drop["tal"], drop["origin"],
                        drop["rating"] or "", drop["id"], "->", keep["name"], keep["club"], keep["age"], keep["over"], keep["tal"], keep["id"]])
    summary = collections.Counter(cls for cls, _x, _y in pairs)
    print("pares encontrados por classe:")
    for cls, n in summary.most_common():
        print(f"  {n:4}  {cls}" + ("" if cls in AUTO else "   (só relatório)"))
    n_del = sum(1 for ln in removed if not by_line[ln]["has_fm"])
    n_unrate = len(removed) - n_del
    print(f"linhas a tratar: {len(removed)} ({n_del} a apagar, {n_unrate} a ficar sem OVER) | relatório: {args.report}")

    if not args.out:
        return
    out = [lines[0]]
    for i, line in enumerate(lines[1:], start=1):
        if i not in removed:
            out.append(line)
            continue
        r = by_line[i]
        if not r["has_fm"]:
            continue  # linha sem dados do FM: apaga-se
        f = split_raw(line)
        for c in GOFOOT_COLS:
            f[CI[c]] = ""
        out.append(";".join(f))
    open(args.out, "wb").write(("\r\n".join(out) + ("\r\n" if ends_nl else "")).encode("latin-1"))
    print("escrito:", args.out)


if __name__ == "__main__":
    sys.exit(main())
