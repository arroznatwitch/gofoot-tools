"""Confirma que o port em Python das fórmulas do site (gofoot_formulas.py) reproduz o players.csv.

Para cada jogador com OVER recalcula o OVER a partir dos atributos, o Valor (OVER, talento, idade, físico) e o
Salário, e compara com o que está no ficheiro. Esperado: Valor e Salário 100%; o OVER pode falhar em linhas
antigas cujo OVER foi escrito à mão (o site recalcula-o sempre a partir dos atributos).

Uso:
    python tools/test_formulas.py --csv players.csv
"""
import argparse
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gofoot_formulas as g  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--csv", required=True)
args = ap.parse_args()


def num(s):
    s = (s or "").strip()
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


tot = ok_over = ok_val = ok_sal = 0
groups = collections.Counter()
bad_over = []
with open(args.csv, encoding="latin-1", newline="") as f:
    for r in csv.DictReader(f, delimiter=";"):
        if not (r.get("OVER") or "").strip():
            continue
        grp = g.posicao_grupo(r.get("Posicao") or r.get("Position"))
        groups[grp] += 1
        attrs = {k: num(r[c]) for k, c in [("TEC", "TEC"), ("ATA", "ATA"), ("DEF", "DEF"), ("FIS", "FIS"),
                                           ("MEN", "MEN"), ("REF", "REF"), ("POS", "POS_GK"), ("AER", "AER"),
                                           ("SAI", "SAI")]}
        over = g.calcular_over(grp, attrs) if grp else None
        tot += 1
        if over == num(r["OVER"]):
            ok_over += 1
        else:
            bad_over.append((r["Name"], r["Club"], grp, over, r["OVER"]))
        valor = g.calcular_valor(grp, over, num(r["TAL"]), num(r["Age"]), attrs["FIS"], attrs["MEN"]) if over is not None else None
        if valor == num(r["Valor"]):
            ok_val += 1
        if g.calcular_salario(over, num(r["Valor"])) == num(r["Salario"]):
            ok_sal += 1

print("jogadores com OVER:", tot, "| grupos:", dict(groups))
print(f"OVER igual à fórmula:    {ok_over} ({ok_over / tot:.1%})")
print(f"Valor igual à fórmula:   {ok_val} ({ok_val / tot:.1%})")
print(f"Salário igual à fórmula: {ok_sal} ({ok_sal / tot:.1%})")
print("exemplos de OVER diferente:", bad_over[:5])
