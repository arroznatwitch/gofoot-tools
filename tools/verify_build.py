"""Verifica o players_new.csv gerado por build_leagues.py contra o players.csv original (só leitura).

Garante, entre outras coisas:
  * nenhuma linha que já tinha OVER foi alterada;
  * só as colunas esperadas mudaram nas linhas completadas;
  * o OVER bate certo com os atributos (fórmula do site), tal como Valor e Salário;
  * Ids únicos, nº de campos, fins de linha e cabeçalho iguais;
  * cada clube novo tem 20+ jogadores completos (regra da aba Ligas) e a média do melhor 11 de cada liga.

Uso:
    python tools/verify_build.py --orig players.csv --new tools/work/out/players_new.csv \\
        --leagues-add tools/work/out/leagues_add.json
"""
import argparse
import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gofoot_formulas as G  # noqa: E402
from common import *  # noqa: E402,F401,F403

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--orig", required=True)
ap.add_argument("--new", required=True)
ap.add_argument("--leagues-add", required=True)
ap.add_argument("--leagues-js", default=os.path.join(HERE, "..", "frontend", "leagues.js"))
args = ap.parse_args()

a_raw = open(args.orig, "rb").read()
b_raw = open(args.new, "rb").read()
a = a_raw.decode("latin-1").split("\r\n")
b = b_raw.decode("latin-1").split("\r\n")
print(f"linhas do original: {len(a)} | do novo: {len(b)} | diferença: {len(b) - len(a)}")
print("mesmo cabeçalho:", a[0] == b[0])
print("original termina com CRLF:", a_raw.endswith(b"\r\n"), "| novo termina com CRLF:", b_raw.endswith(b"\r\n"))
assert a[0] == b[0]
assert a_raw.endswith(b"\r\n") == b_raw.endswith(b"\r\n")
assert b_raw.count(b"\n") == b_raw.count(b"\r\n"), "há fins de linha LF soltos"
assert all(len(split_raw(x)) == 32 for x in b[1:]), "linha com número errado de campos"

# 1) linhas já avaliadas intactas; só as colunas esperadas mudam
n_orig = len(a) - 1
changed, rated_changed = [], []
for i in range(1, len(a)):
    if a[i] != b[i]:
        changed.append(i)
        if unquote(split_raw(a[i])[CI["OVER"]]).strip() != "":
            rated_changed.append(i)
print(f"linhas do original que mudaram: {len(changed)} | destas, já com OVER (têm de ser 0): {len(rated_changed)}")
assert not rated_changed, rated_changed[:5]

cols_changed = collections.Counter()
for i in changed:
    fa, fb = split_raw(a[i]), split_raw(b[i])
    for k, (x, y) in enumerate(zip(fa, fb)):
        if x != y:
            cols_changed[COLS[k]] += 1
print("colunas alteradas:", dict(cols_changed))
allowed = {"Name", "Club", "Nation", "Age", "Pe", "Posicao", "TAL", "Valor", "TEC", "ATA", "DEF", "FIS", "MEN",
           "REF", "POS_GK", "AER", "SAI", "OVER", "Salario"}
assert not (set(cols_changed) - allowed), set(cols_changed) - allowed
for i in changed:
    assert unquote(split_raw(a[i])[CI["OVER"]]).strip() == ""
new_rows = b[1 + n_orig:]
print("linhas acrescentadas:", len(new_rows))

# 2) consistência de todas as linhas completadas/acrescentadas
ids = collections.Counter(unquote(split_raw(line)[CI["Id"]]) for line in b[1:])
dups = [k for k, v in ids.items() if v > 1]
print("Ids duplicados no ficheiro todo (têm de ser 0):", len(dups))
assert not dups


def num(s):
    s = (s or "").strip()
    return int(s) if s.lstrip("-").isdigit() else None


def attrs_of(f):
    return {k: num(unquote(f[CI[c]])) for k, c in [("TEC", "TEC"), ("ATA", "ATA"), ("DEF", "DEF"), ("FIS", "FIS"),
                                                   ("MEN", "MEN"), ("REF", "REF"), ("POS", "POS_GK"),
                                                   ("AER", "AER"), ("SAI", "SAI")]}


problems = collections.Counter()
over_vals, by_grp = [], collections.Counter()
for f in [split_raw(b[i]) for i in changed] + [split_raw(x) for x in new_rows]:
    grp = unquote(f[CI["Posicao"]])
    if grp not in G.GRUPOS_VALIDOS:
        problems["posicao_invalida"] += 1
        continue
    by_grp[grp] += 1
    at = attrs_of(f)
    over = G.calcular_over(grp, at)
    if over is None or over != num(unquote(f[CI["OVER"]])):
        problems["over_diferente_da_formula"] += 1
    for k in G.attr_keys(grp):
        if at[k] is None or not (1 <= at[k] <= 99):
            problems["atributo_fora_do_intervalo"] += 1
    if any(at[k] is not None for k in at if k not in G.attr_keys(grp)):
        problems["atributos_a_mais_para_a_posicao"] += 1
    tal, age = num(unquote(f[CI["TAL"]])), num(unquote(f[CI["Age"]]))
    if tal is None or not (30 <= tal <= 99):
        problems["tal_invalido"] += 1
    if age is None or not (14 <= age <= 45):
        problems["idade_invalida"] += 1
    valor = G.calcular_valor(grp, over, tal, age, at["FIS"], at["MEN"])
    if valor != num(unquote(f[CI["Valor"]])):
        problems["valor_diferente_da_formula"] += 1
    if G.calcular_salario(over, valor) != num(unquote(f[CI["Salario"]])):
        problems["salario_diferente_da_formula"] += 1
    if unquote(f[CI["Pe"]]) not in ("D", "E", "A"):
        problems["pe_invalido"] += 1
    over_vals.append(over)
print("linhas verificadas:", len(over_vals), "| por grupo:", dict(by_grp))
print("problemas (têm de ser 0):", dict(problems))
assert not problems

# 3) regra da aba Ligas: 20+ jogadores completos por clube
add = json.load(open(args.leagues_add, encoding="utf-8"))
per_club = collections.defaultdict(list)
for line in b[1:]:
    f = split_raw(line)
    grp = G.posicao_grupo(unquote(f[CI["Posicao"]]) or unquote(f[CI["Position"]]))
    if not grp:
        continue
    over = G.calcular_over(grp, attrs_of(f))
    if over is not None:
        per_club[slug(unquote(f[CI["Club"]]))].append((grp, over))

FORMACAO = [(["G"], 1), (["L"], 2), (["Z"], 2), (["V", "M"], 4), (["PE", "CA", "PD"], 2)]


def xi_over(players):
    chosen = []
    for grupos, n in FORMACAO:
        chosen += sorted((o for g, o in players if g in grupos), reverse=True)[:n]
    return round(sum(chosen) / len(chosen)) if chosen else None


def league_summary(label, clubs):
    sizes = [len(per_club.get(slug(c), [])) for c in clubs]
    xis = [xi_over(per_club[slug(c)]) for c in clubs if len(per_club.get(slug(c), [])) >= 20]
    short = [(c, n) for c, n in zip(clubs, sizes) if n < 20]
    media = f"{statistics.mean(xis):5.1f}" if xis else "  n/d"
    print(f"   {label:40} clubes={len(clubs):2} jogadores/clube min={min(sizes):2} med={statistics.median(sizes):4.1f}"
          f" max={max(sizes):2} | média OVR do melhor 11={media}" + (f" | ABAIXO DE 20: {short}" if short else ""))
    return short


print("ligas novas (20+ completos por clube) e média OVR do melhor 11:")
below = []
for country, leagues in add.items():
    for ln, clubs in leagues.items():
        below += league_summary(f"NOVA {country} / {ln}", clubs)
if os.path.exists(args.leagues_js):
    existing = load_leagues_js(args.leagues_js)
    print("ligas já existentes, para comparar:")
    for country, leagues in existing.items():
        if country in add:
            continue
        for ln, clubs in leagues.items():
            league_summary(f"{country} / {ln}", clubs)
assert not below, below

print("OVER das linhas completadas/novas: mín", min(over_vals), "mediana", statistics.median(over_vals), "máx", max(over_vals))
print("tudo certo: todas as verificações passaram")
