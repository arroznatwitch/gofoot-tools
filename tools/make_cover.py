"""Gera o cover 1280x720 do patch portugal_2026 (logos das competições do próprio patch + texto)."""
import json
import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PATCH = sys.argv[1]
OUT = sys.argv[2]
W, H, S = 1280, 720, 2  # S = supersampling
F = "C:/Windows/Fonts/"
VERDE, VERMELHO, OURO, CREME = (0, 102, 51), (200, 16, 46), (255, 204, 0), (245, 241, 230)


def fonte(nome, tam):
    return ImageFont.truetype(F + nome, tam * S)


comps = {c["id"]: c for c in json.load(open(os.path.join(PATCH, "data", "competitions.json"), encoding="utf-8"))["competitions"]}
ordem = ["af_national_division_1", "af_national_division_2", "af_national_division_3", "af_national_division_4"]
copas = [i for i in comps if i not in ordem]  # taça de portugal, taça da liga, supertaça
logos = []
for cid in ordem + copas:
    p = os.path.join(PATCH, "images", "competitions", comps[cid].get("logo_image") or "")
    if os.path.isfile(p):
        logos.append((comps[cid]["name"], Image.open(p).convert("RGBA")))

img = Image.new("RGB", (W * S, H * S), (8, 24, 16))
d = ImageDraw.Draw(img)
# fundo: faixa vermelha e verde na diagonal, com sombra
for y in range(H * S):
    t = y / (H * S)
    d.line([(0, y), (W * S, y)], fill=(int(6 + 10 * t), int(30 + 40 * (1 - t)), int(18 + 14 * (1 - t))))
poli = Image.new("RGBA", img.size, (0, 0, 0, 0))
pd = ImageDraw.Draw(poli)
pd.polygon([(0, 0), (int(.42 * W * S), 0), (int(.28 * W * S), H * S), (0, H * S)], fill=VERDE + (255,))
pd.polygon([(int(.42 * W * S), 0), (int(.50 * W * S), 0), (int(.36 * W * S), H * S), (int(.28 * W * S), H * S)], fill=VERMELHO + (255,))
sombra = poli.filter(ImageFilter.GaussianBlur(14 * S))
img.paste(Image.new("RGB", img.size, (0, 0, 0)), (22 * S, 0), sombra.split()[3].point(lambda v: v // 2))
img.paste(poli, (0, 0), poli)
d = ImageDraw.Draw(img)

# texto
x = 64 * S
d.text((x, 92 * S), "PATCH DO GOFOOT", font=fonte("segoeuib.ttf", 26), fill=OURO)
d.text((x, 130 * S), "PORTUGAL", font=fonte("impact.ttf", 150), fill=CREME)
d.text((x, 292 * S), "2026/27", font=fonte("impact.ttf", 96), fill=OURO)
d.rectangle([x, 424 * S, x + 150 * S, 430 * S], fill=CREME)
d.text((x, 446 * S), "+112 equipas · 4 divisões · 3 taças", font=fonte("segoeuib.ttf", 28), fill=CREME)
d.text((x, 488 * S), "Liga Portugal Betclic · Liga Portugal 2 · Liga 3 · Campeonato de Portugal", font=fonte("segoeui.ttf", 19), fill=(220, 235, 225))
d.text((x, 518 * S), "Taça de Portugal · Taça da Liga · Supertaça Cândido de Oliveira", font=fonte("segoeui.ttf", 19), fill=(220, 235, 225))
d.text((x, 650 * S), "Atualizado a 27/10/2026 · por ArrozNaTwitch", font=fonte("segoeui.ttf", 18), fill=(200, 220, 210))

# logos: grelha 4 + 3 à direita
ex, ey, cel = 700, 120, 128
gap = 16
pos = []
for i in range(len(logos)):
    linha, col = (0, i) if i < 4 else (1, i - 4)
    n = 4 if linha == 0 else len(logos) - 4
    inicio = ex + (4 - n) * (cel + gap) // 2 if linha else ex
    pos.append((inicio + col * (cel + gap), ey + linha * (cel + gap + 60) + (0 if linha == 0 else 20)))
for (nome, lg), (px, py) in zip(logos, pos):
    cartao = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cartao)
    cd.rounded_rectangle([px * S, py * S, (px + cel) * S, (py + cel) * S], radius=18 * S, fill=(245, 241, 230, 235))
    img.paste(cartao, (0, 0), cartao)
    l = lg.copy()
    l.thumbnail(((cel - 24) * S, (cel - 24) * S), Image.LANCZOS)
    img.paste(l, ((px + cel // 2) * S - l.width // 2, (py + cel // 2) * S - l.height // 2), l)
d = ImageDraw.Draw(img)

img = img.resize((W, H), Image.LANCZOS)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
img.save(OUT, optimize=True)
print(OUT, img.size, len(logos), "logos")
