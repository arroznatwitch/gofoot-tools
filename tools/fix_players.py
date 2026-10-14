"""Correções pedidas ao players.csv em 14-10-2026. Só mexe nas colunas indicadas; o resto das linhas fica byte a byte igual.

1. Pé dos extremos: quem tem Posicao PE (ponta esquerda) e pé direito passa a pé esquerdo; quem tem PD (ponta direita) e pé
   esquerdo passa a pé direito. Ambidestros (A) ficam como estão. O pé não entra no OVER, no Valor nem no Salário.
2. Posições do Estoril Praia: João Carvalho, Holsgrove e Bernardo Lourenço passam a M e Begraoui a CA. O site calcula o OVER
   com os atributos e o grupo da posição, por isso, onde o novo grupo daria outro OVER, ajustam-se o mínimo possível o TEC e o
   ATA para o OVER ficar igual (Valor e Salário não mudam, só dependem do OVER, TAL e idade).

Uso:
    python tools/fix_players.py --csv players.csv --out tools/work/players_fixed.csv
    python tools/fix_players.py --csv players.csv --check        (só mostra o que mudaria)
"""
import argparse
import collections
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gofoot_formulas as G  # noqa: E402
from common import CI, COLS, encode_field, split_raw, unquote, wing_foot  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# (Id, nome no CSV, clube, grupo novo)
POSITION_FIXES = [
    ("joaocarvalho_xfy55q9r", "Carvalho, João", "Estoril Praia", "M"),
    ("jordanholsgrove_n57nfhzu", "Holsgrove, Jordan", "Estoril Praia", "M"),
    ("yanisbegraoui_eljqkfo6", "Begraoui, Yanis", "Estoril Praia", "CA"),
    ("bernardolourenco_m007dwxe", "Lourenço, Bernardo", "Estoril Praia", "M"),
]
ATTR_COLS = {"TEC": "TEC", "ATA": "ATA", "DEF": "DEF", "FIS": "FIS", "MEN": "MEN"}


def num(s):
    s = (s or "").strip()
    return int(s) if s.lstrip("-").isdigit() else None


def retarget(grp, attrs, target):
    """Menores alterações em TEC/ATA (maior alteração mínima, depois soma mínima) para a fórmula do grupo dar `target`."""
    if G.calcular_over(grp, attrs) == target:
        return dict(attrs)
    best = None
    for dt, da in itertools.product(range(-12, 13), repeat=2):
        cand = dict(attrs, TEC=attrs["TEC"] + dt, ATA=attrs["ATA"] + da)
        if not (1 <= cand["TEC"] <= 99 and 1 <= cand["ATA"] <= 99) or G.calcular_over(grp, cand) != target:
            continue
        key = (max(abs(dt), abs(da)), abs(dt) + abs(da), abs(dt - da))
        if best is None or key < best[0]:
            best = (key, cand)
    if best is None:
        raise SystemExit(f"não consegui chegar ao OVER {target} no grupo {grp} com {attrs}")
    return best[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", help="ficheiro de saída (sem isto, só mostra o que mudaria)")
    ap.add_argument("--check", action="store_true", help="não escreve nada")
    args = ap.parse_args()

    raw = open(args.csv, "rb").read().decode("latin-1")
    ends_nl = raw.endswith("\r\n")
    lines = raw.split("\r\n")
    if ends_nl:
        lines.pop()
    assert split_raw(lines[0]) == COLS, "cabeçalho inesperado"
    fixes = {i: (nm, club, new) for i, nm, club, new in POSITION_FIXES}
    seen = set()
    flips = collections.Counter()
    out = [lines[0]]
    changed_rows = 0
    for line in lines[1:]:
        f = split_raw(line)
        ident = unquote(f[CI["Id"]])
        before = line
        if ident in fixes:
            nm, club, new = fixes[ident]
            assert unquote(f[CI["Name"]]) == nm and unquote(f[CI["Club"]]) == club, (ident, f[CI["Name"]], f[CI["Club"]])
            old = unquote(f[CI["Posicao"]])
            over = num(unquote(f[CI["OVER"]]))
            attrs = {k: num(unquote(f[CI[c]])) for k, c in ATTR_COLS.items()}
            age, tal = num(unquote(f[CI["Age"]])), num(unquote(f[CI["TAL"]]))
            valor, sal = num(unquote(f[CI["Valor"]])), num(unquote(f[CI["Salario"]]))
            assert G.calcular_over(old, attrs) == over, (nm, old, over)  # a linha estava coerente com a fórmula
            newattrs = retarget(new, attrs, over)
            assert G.calcular_valor(new, over, tal, age, newattrs["FIS"], newattrs["MEN"]) == valor
            assert G.calcular_salario(over, valor) == sal
            f[CI["Posicao"]] = encode_field(new)
            for k, c in ATTR_COLS.items():
                f[CI[c]] = encode_field(str(newattrs[k]))
            seen.add(ident)
            extra = {k: f"{attrs[k]}->{newattrs[k]}" for k in attrs if attrs[k] != newattrs[k]}
            print(f"{nm:20} {club}: {old} -> {new} | OVER {over} (fórmula do grupo antigo {G.calcular_over(old, attrs)}, "
                  f"do novo com os atributos antigos {G.calcular_over(new, attrs)}) | atributos alterados: {extra or 'nenhum'}")
        grp = G.posicao_grupo(unquote(f[CI["Posicao"]]))  # com a posição já corrigida
        foot = unquote(f[CI["Pe"]])
        if grp in ("PE", "PD") and foot in ("D", "E"):
            new_foot = wing_foot(grp, foot)
            flips[(grp, foot, new_foot)] += 1
            if new_foot != foot:
                f[CI["Pe"]] = encode_field(new_foot)
        newline = ";".join(f)
        changed_rows += newline != before
        out.append(newline)
    assert seen == set(fixes), set(fixes) - seen
    print("extremos por grupo e pé (grupo, pé antes, pé depois): linhas")
    for k in sorted(flips):
        print("  ", k, flips[k])
    print("linhas alteradas:", changed_rows)
    if args.out and not args.check:
        text = "\r\n".join(out) + ("\r\n" if ends_nl else "")
        open(args.out, "wb").write(text.encode("latin-1"))
        print("escrito:", args.out)


if __name__ == "__main__":
    sys.exit(main())
