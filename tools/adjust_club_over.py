"""Baixa (ou sobe) o OVER de todos os jogadores completos de alguns clubes, uma quantidade fixa por clube.

O site calcula o OVER com os atributos e o grupo da posição (os pesos somam 1), por isso o script tira (ou põe) k pontos a
cada atributo da fórmula do grupo e o OVER muda exatamente k. Valor e Salário voltam a calcular-se com as fórmulas do site
(OVER novo, TAL e idade iguais). TAL, posição, pé, idade e o resto da linha não mudam; linhas sem OVER ficam como estão.

Uso:
    python tools/adjust_club_over.py --csv players.csv --out tools/work/players_adj.csv \\
        --club "Nacional da Madeira=-2" --club "Rio Ave=-3"
    (sem --out só mostra o antes e o depois, como aparece nos cartões da aba Ligas: OVR/ATA/MEI/DEF do melhor 11)
"""
import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gofoot_formulas as G  # noqa: E402
from common import CI, COLS, clamp, encode_field, slug, split_raw, unquote  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
COLUMN = {"TEC": "TEC", "ATA": "ATA", "DEF": "DEF", "FIS": "FIS", "MEN": "MEN", "REF": "REF", "POS": "POS_GK",
          "AER": "AER", "SAI": "SAI"}
XI = [(["G"], 1, "def"), (["L"], 2, "def"), (["Z"], 2, "def"), (["V", "M"], 4, "mei"), (["PE", "CA", "PD"], 2, "ata")]


def num(s):
    s = (s or "").strip()
    return int(s) if s.lstrip("-").isdigit() else None


def grupo_e_atributos(f):
    grp = G.posicao_grupo(unquote(f[CI["Posicao"]]) or unquote(f[CI["Position"]]))
    if grp is None:
        return None, None
    return grp, {k: num(unquote(f[CI[COLUMN[k]]])) for k in G.attr_keys(grp)}


def shift_attrs(grp, attrs, target, delta):
    """Soma delta a cada atributo da fórmula e acerta os arredondamentos até a fórmula dar exatamente `target`."""
    keys = G.attr_keys(grp)
    new = {k: int(clamp(attrs[k] + delta, 1, 99)) for k in keys}
    guard = 0
    while G.calcular_over(grp, new) != target and guard < 200:
        guard += 1
        up = G.calcular_over(grp, new) < target
        cand = sorted(keys, key=lambda k: G.OVER_WEIGHTS[grp][k], reverse=True)
        for k in cand:
            nv = new[k] + (1 if up else -1)
            if 1 <= nv <= 99:
                new[k] = nv
                break
        else:
            break
    assert G.calcular_over(grp, new) == target, (grp, attrs, target)
    return new


def card(overs_by_group):
    """OVR/ATA/MEI/DEF como na aba Ligas (média arredondada do melhor 11) e a média sem arredondar."""
    lines = collections.defaultdict(list)
    for grupos, n, linha in XI:
        pool = sorted((o for g in grupos for o in overs_by_group.get(g, [])), reverse=True)[:n]
        lines[linha] += pool
    xi = lines["def"] + lines["mei"] + lines["ata"]
    avg = lambda a: int(sum(a) / len(a) + 0.5) if a else None  # noqa: E731
    return avg(xi), avg(lines["ata"]), avg(lines["mei"]), avg(lines["def"]), (sum(xi) / len(xi) if xi else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", help="ficheiro de saída (sem isto só mostra o antes e o depois)")
    ap.add_argument("--club", action="append", required=True, metavar="CLUBE=DELTA",
                    help='ex.: "Rio Ave=-3" (repetir para vários clubes)')
    args = ap.parse_args()
    deltas = {}
    for item in args.club:
        name, _, d = item.rpartition("=")
        deltas[slug(name)] = (name, int(d))

    raw = open(args.csv, "rb").read().decode("latin-1")
    ends_nl = raw.endswith("\r\n")
    lines = raw.split("\r\n")
    if ends_nl:
        lines.pop()
    assert split_raw(lines[0]) == COLS, "cabeçalho inesperado"
    before, after = collections.defaultdict(lambda: collections.defaultdict(list)), \
        collections.defaultdict(lambda: collections.defaultdict(list))
    seen, changed, off_formula = collections.Counter(), 0, collections.Counter()
    out = [lines[0]]
    for line in lines[1:]:
        f = split_raw(line)
        s = slug(unquote(f[CI["Club"]]))
        if s not in deltas:
            out.append(line)
            continue
        grp, attrs = grupo_e_atributos(f)
        over = G.calcular_over(grp, attrs) if grp else None
        if over is None:
            out.append(line)  # linha sem OVER (incompleta): não aparece no site
            continue
        name, delta = deltas[s]
        age, tal = num(unquote(f[CI["Age"]])), num(unquote(f[CI["TAL"]]))
        old_valor = num(unquote(f[CI["Valor"]]))
        if G.calcular_valor(grp, over, tal, age, attrs.get("FIS"), attrs.get("MEN")) != old_valor:
            off_formula[name] += 1
        target = int(clamp(over + delta, 1, 99))
        new = shift_attrs(grp, attrs, target, delta)
        valor = G.calcular_valor(grp, target, tal, age, new.get("FIS"), new.get("MEN"))
        for k, v in new.items():
            f[CI[COLUMN[k]]] = encode_field(str(v))
        f[CI["OVER"]] = encode_field(str(target))
        f[CI["Valor"]] = encode_field(str(valor))
        f[CI["Salario"]] = encode_field(str(G.calcular_salario(target, valor)))
        before[name][grp].append(over)
        after[name][grp].append(target)
        seen[name] += 1
        changed += 1
        out.append(";".join(f))
    missing = [n for n, _d in deltas.values() if seen[n] == 0]
    assert not missing, f"clubes sem jogadores completos: {missing}"
    print(f"{'clube':26} {'jogadores':>9} {'antes OVR/ATA/MEI/DEF':>24} {'depois':>22}")
    for name, delta in deltas.values():
        b, a = card(before[name]), card(after[name])
        print(f"{name:26} {seen[name]:9} {b[0]}/{b[1]}/{b[2]}/{b[3]} ({b[4]:.2f}) {'->':>3} {a[0]}/{a[1]}/{a[2]}/{a[3]} ({a[4]:.2f})"
              f"  delta {delta:+d}")
    if off_formula:
        print("aviso: Valor guardado diferente da fórmula antes da alteração:", dict(off_formula))
    print("linhas alteradas:", changed)
    if args.out:
        text = "\r\n".join(out) + ("\r\n" if ends_nl else "")
        open(args.out, "wb").write(text.encode("latin-1"))
        print("escrito:", args.out)


if __name__ == "__main__":
    sys.exit(main())
