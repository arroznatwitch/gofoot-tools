"""Descarrega do Transfermarkt os clubes de cada liga (época indicada no config.json) e os respetivos plantéis.

Para cada clube guarda: nome, data de nascimento, idade, nacionalidades (a primeira é a principal), pé, posição,
valor de mercado, de onde veio, etc. As páginas ficam em cache (--cache-dir), por isso repetir o script não volta
a pedir ao site. Faz uma pausa de ~1 s entre pedidos; não aumentes o ritmo.

Uso:
    python tools/fetch_transfermarkt.py --out tools/work/tm_squads.json --cache-dir tools/work/tm_raw
"""
import argparse
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def get(url, cache_path):
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 5000:
        return open(cache_path, encoding="utf-8", errors="replace").read()
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read().decode("utf-8", errors="replace")
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(data)
            time.sleep(1.0)
            return data
        except urllib.error.HTTPError as e:
            print("  HTTP", e.code, url, "tentativa", attempt, flush=True)
            time.sleep(5 + attempt * 5)
        except Exception as e:  # noqa: BLE001
            print("  erro", e, url, "tentativa", attempt, flush=True)
            time.sleep(3 + attempt * 3)
    raise SystemExit("falhou: " + url)


def clean(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse_money(s):
    s = clean(s).replace("€", "").replace(",", "").strip()
    m = re.match(r"^([\d.]+)\s*(bn|m|k|th\.)?$", s, re.I)
    if not m:
        return None
    v = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit == "bn":
        v *= 1e9
    elif unit == "m":
        v *= 1e6
    elif unit in ("k", "th."):
        v *= 1e3
    return int(round(v))


def parse_clubs(page):
    out, seen = [], set()
    pattern = (r'<td class="hauptlink no-border-links"><a title="([^"]+)" '
               r'href="(/([^/"]+)/startseite/verein/(\d+)/saison_id/(\d+))"')
    for m in re.finditer(pattern, page):
        title, _href, slug, cid, _season = m.groups()
        if cid in seen:
            continue
        seen.add(cid)
        out.append({"name": htmllib.unescape(title).strip(), "slug": slug, "id": int(cid)})
    return out


def parse_squad(page):
    i = page.find('<table class="items">')
    if i < 0:
        return []
    j = page.find("</table>", page.find("</tbody>", i))
    tbl = page[i:j]
    starts = [m.start() for m in re.finditer(r'<tr class="(?:odd|even)">', tbl)]
    rows = []
    for k, s in enumerate(starts):
        chunk = tbl[s:(starts[k + 1] if k + 1 < len(starts) else len(tbl))]
        nm = re.search(r'<td class="hauptlink">\s*<a href="/([^"]+)/profil/spieler/(\d+)">\s*(.*?)\s*</a>', chunk, re.S)
        if not nm:
            continue
        inline = re.search(r'<table class="inline-table">(.*?)</table>', chunk, re.S)
        pos = None
        if inline:
            pm = re.findall(r"<td>\s*([^<]+?)\s*</td>", inline.group(1))
            pos = clean(pm[-1]) if pm else None
        rest = re.sub(r'<table class="inline-table">.*?</table>', "", chunk, flags=re.S)
        num = re.search(r"<div class=rn_nummer>([^<]*)</div>", rest)
        tds = re.findall(r'<td class="zentriert"[^>]*>(.*?)</td>', rest, re.S)
        dob = re.search(r"(\d{2})/(\d{2})/(\d{4})\s*\((\d+)\)", clean(tds[0] if tds else ""))
        nats = [htmllib.unescape(x) for x in
                re.findall(r'title="([^"]+)"[^>]*class="flaggenrahmen"', tds[1] if len(tds) > 1 else "")]
        from_m = re.search(r'title="([^"]+)"[^>]*class=""', tds[5]) if len(tds) > 5 else None
        val_m = re.search(r'<td class="rechts hauptlink">(.*?)</td>', rest, re.S)
        loan_m = re.search(r'title="(On loan from [^"]+)"', chunk)
        rows.append({
            "tm_id": int(nm.group(2)),
            "slug": nm.group(1),
            "name": clean(nm.group(3)),
            "num": clean(num.group(1)) if num else "",
            "pos": pos,
            "dob": f"{dob.group(3)}-{dob.group(2)}-{dob.group(1)}" if dob else None,
            "age": int(dob.group(4)) if dob else None,
            "nats": nats,
            "height": clean(tds[2]) if len(tds) > 2 else "",
            "foot": clean(tds[3]).lower() if len(tds) > 3 else "",
            "joined": clean(tds[4]) if len(tds) > 4 else "",
            "signed_from": htmllib.unescape(from_m.group(1)) if from_m else None,
            "contract": clean(tds[6]) if len(tds) > 6 else "",
            "value": parse_money(val_m.group(1)) if val_m else None,
            "on_loan_from": loan_m.group(1) if loan_m else None,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--out", required=True, help="ficheiro .json de saída (plantéis)")
    ap.add_argument("--cache-dir", required=True, help="pasta onde guardar o HTML descarregado")
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8"))
    season = cfg["season"]
    os.makedirs(args.cache_dir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    result = []
    for lg in cfg["leagues"]:
        url = (f"https://www.transfermarkt.com/{lg['tm_slug']}/startseite/wettbewerb/{lg['tm_code']}"
               f"/plus/?saison_id={season}")
        page = get(url, os.path.join(args.cache_dir, f"league_{lg['tm_code']}.html"))
        clubs = parse_clubs(page)
        print(f"{lg['country']} / {lg['league']}: {len(clubs)} clubes", flush=True)
        for c in clubs:
            sq = get(f"https://www.transfermarkt.com/{c['slug']}/kader/verein/{c['id']}/saison_id/{season}/plus/1",
                     os.path.join(args.cache_dir, f"squad_{c['id']}.html"))
            players = parse_squad(sq)
            print(f"   {c['name']:28} jogadores={len(players)}", flush=True)
            result.append({"country": lg["country"], "league": lg["league"], "code": lg["tm_code"],
                           "site_label": lg["site_label"], **c, "players": players})
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print("clubes:", len(result), "| jogadores:", sum(len(c["players"]) for c in result))


if __name__ == "__main__":
    sys.exit(main())
