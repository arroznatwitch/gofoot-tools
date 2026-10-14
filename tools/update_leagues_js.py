"""Acrescenta ao frontend/leagues.js as ligas novas (leagues_add.json, criado por build_leagues.py).

Não mexe no resto do ficheiro, mantém os fins de linha (CRLF) e é idempotente: países que já existem são
ignorados. O nome da liga no site vem do campo "site_label" do config.json.

Uso:
    python tools/update_leagues_js.py --add tools/work/out/leagues_add.json --before Suécia
(sem --before os países novos vão para o fim do ficheiro)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import load_leagues_js  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--add", required=True, help="leagues_add.json")
ap.add_argument("--js", default=os.path.join(HERE, "..", "frontend", "leagues.js"))
ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
ap.add_argument("--before", default=None, help="país antes do qual inserir os novos (ex.: Suécia)")
args = ap.parse_args()

cfg = json.load(open(args.config, encoding="utf-8"))
label = {(lg["country"], lg["league"]): lg["site_label"] for lg in cfg["leagues"]}
add = json.load(open(args.add, encoding="utf-8"))
text = open(args.js, "rb").read().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
existing = load_leagues_js(args.js)

blocks = []
for country, leagues in add.items():
    if country in existing:
        print("já existe, ignorado:", country)
        continue
    for lg, clubs in leagues.items():
        rows = ["        " + ", ".join('"%s"' % c for c in clubs[i:i + 4]) for i in range(0, len(clubs), 4)]
        body = ", \n".join(rows)
        blocks.append('"%s": {\n    "%s": [\n%s\n    ]\n},\n' % (country, label[(country, lg)], body))
if not blocks:
    print("nada para acrescentar")
    sys.exit(0)

new = "".join(blocks).replace("\n", nl)
anchor = '"%s": {' % args.before if args.before else None
if anchor and text.count(anchor) == 1:
    out = text.replace(anchor, new + anchor, 1)
else:
    if anchor:
        print("país âncora não encontrado; a acrescentar no fim")
    end = text.rindex("}")
    head = text[:end].rstrip()
    assert head.endswith("}"), "formato inesperado do leagues.js"
    out = head + "," + nl + new.rstrip().rstrip(",") + nl + text[end:]
open(args.js, "wb").write(out.encode("utf-8"))
print("acrescentados %d bloco(s) a %s" % (len(blocks), args.js))
