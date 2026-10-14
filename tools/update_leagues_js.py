"""Acrescenta ao frontend/leagues.js as ligas novas (leagues_add.json, criado por build_leagues.py).

Não mexe no resto do ficheiro, mantém os fins de linha (CRLF) e é idempotente: ligas que já existem são
ignoradas. O nome da liga no site vem do campo "site_label" do config.json. Um país novo ganha um bloco novo; uma liga
nova de um país que já existe (ex.: a Série D dentro de "Brasil") entra no bloco desse país, a seguir à última liga.

Uso:
    python tools/update_leagues_js.py --add tools/work/out/leagues_add.json --before Suécia
    python tools/update_leagues_js.py --add tools/work/out_d/leagues_add.json --config tools/config_serie_d.json --per-row 6
(sem --before os países novos vão para o fim do ficheiro)
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import load_leagues_js  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--add", required=True, help="leagues_add.json")
ap.add_argument("--js", default=os.path.join(HERE, "..", "frontend", "leagues.js"))
ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
ap.add_argument("--before", default=None, help="país antes do qual inserir os países novos (ex.: Suécia)")
ap.add_argument("--per-row", type=int, default=4, help="clubes por linha no ficheiro (por defeito 4)")
args = ap.parse_args()

cfg = json.load(open(args.config, encoding="utf-8"))
label = {(lg["country"], lg["league"]): lg["site_label"] for lg in cfg["leagues"]}
add = json.load(open(args.add, encoding="utf-8"))
text = open(args.js, "rb").read().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
existing = load_leagues_js(args.js)
n = args.per_row


def club_rows(clubs, indent):
    rows = [indent + ", ".join('"%s"' % c for c in clubs[i:i + n]) for i in range(0, len(clubs), n)]
    return ", \n".join(rows)


def block_end(txt, country):
    """(início do conteúdo, posição do '}' que fecha) do bloco de um país."""
    found = list(re.finditer(r'"%s"\s*:\s*\{' % re.escape(country), txt))
    assert len(found) == 1, "país %r aparece %d vezes no leagues.js" % (country, len(found))
    start = found[0].end()
    depth, i, in_str = 1, start, False
    while depth:
        ch = txt[i]
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            depth += (ch == "{") - (ch == "}")
        i += 1
    return start, i - 1


new_blocks, added_to_existing = [], 0
for country, leagues in add.items():
    todo = {lg: clubs for lg, clubs in leagues.items() if label[(country, lg)] not in existing.get(country, {})}
    for lg in leagues:
        if lg not in todo:
            print("já existe, ignorado:", label[(country, lg)])
    if not todo:
        continue
    if country not in existing:
        parts = ['    "%s": [\n%s\n    ]' % (label[(country, lg)], club_rows(clubs, "        ")) for lg, clubs in todo.items()]
        new_blocks.append('"%s": {\n%s\n},\n' % (country, ",\n".join(parts)))
        continue
    for lg, clubs in todo.items():  # país que já existe: a liga entra no bloco dele, a seguir à última
        start, close = block_end(text, country)
        keys = re.findall(r'^([ \t]*)"[^"\n]+"\s*:\s*\[', text[start:close], re.M)
        indent = keys[-1] if keys else "    "
        last = text.rindex("]", start, close)
        piece = ("," + nl + indent + '"%s": [' + nl + "%s" + nl + indent + "]") % (
            label[(country, lg)], club_rows(clubs, indent + "    ").replace("\n", nl))
        text = text[:last + 1] + piece + text[last + 1:]  # depois do ']' da última liga
        added_to_existing += 1
        print("liga %r acrescentada ao bloco de %s" % (label[(country, lg)], country))

if new_blocks:
    block = "".join(new_blocks).replace("\n", nl)
    anchor = '"%s": {' % args.before if args.before else None
    if anchor and text.count(anchor) == 1:
        text = text.replace(anchor, block + anchor, 1)
    else:
        if anchor:
            print("país âncora não encontrado; a acrescentar no fim")
        end = text.rindex("}")
        head = text[:end].rstrip()
        assert head.endswith("}"), "formato inesperado do leagues.js"
        text = head + "," + nl + block.rstrip().rstrip(",") + nl + text[end:]
if not new_blocks and not added_to_existing:
    print("nada para acrescentar")
    sys.exit(0)
open(args.js, "wb").write(text.encode("utf-8"))
print("acrescentados %d bloco(s) de países e %d liga(s) a países existentes em %s" % (len(new_blocks), added_to_existing, args.js))
