"""Funções de apoio: normalização de texto, leitura "crua" do players.csv, mapas de nacionalidades
e posições, interpolação e leitura do frontend/leagues.js."""
import difflib
import json
import re
import unicodedata

COLS = ["Gen", "Name", "Nation", "Position", "Club", "Age", "Con", "Jdns", "Happiness Level", "Int Caps",
        "Int Goals", "Wage", "Value", "Sale Value", "Best Rating", "Best Pot Rating", "Id", "Pe", "Posicao",
        "TAL", "Valor", "TEC", "ATA", "DEF", "FIS", "MEN", "REF", "POS_GK", "AER", "SAI", "OVER", "Salario"]
CI = {c: i for i, c in enumerate(COLS)}

# ----------------------------------------------------------------------------- text
_TRANS = str.maketrans({
    "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "ß": "ss", "đ": "d", "Đ": "d",
    "ł": "l", "Ł": "l", "þ": "th", "Þ": "th", "ð": "d", "Ð": "d", "ı": "i", "İ": "i", "ħ": "h",
})


def strip_accents(s):
    s = (s or "").translate(_TRANS)
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_text(s):
    t = strip_accents(s).lower()
    t = re.sub(r"['’‘`´]", "", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def slug(s):
    """Same as slugifyClube() in script.js."""
    return re.sub(r"[^a-z0-9]+", "_", strip_accents(s).lower().strip()).strip("_")


PARTICLES = {"de", "da", "do", "dos", "das", "van", "von", "der", "den", "di", "del", "della", "la", "le", "el",
             "al", "bin", "ben", "ibn", "jr", "junior", "y", "e", "du", "des", "ter", "ten", "te", "ul", "el"}
GENERIC_CLUB = {"fc", "ac", "as", "ss", "us", "sc", "cf", "fk", "sk", "kv", "kvc", "krc", "kaa", "rc", "rsc", "afc",
                "sv", "ssc", "acf", "og", "ogc", "aj", "ud", "cd", "ca", "club", "de", "la", "le", "1907", "1909"}


def tokens(s):
    return norm_text(s).split()


def eff_tokens(s):
    return [t for t in tokens(s) if t not in PARTICLES and len(t) >= 2]


def _lev1(a, b):
    """True if the edit distance between a and b is <= 1."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    if la > lb:
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def tok_eq(a, b):
    if a == b:
        return True
    if len(a) >= 5 and len(b) >= 5:
        if _lev1(a, b):
            return True
        if a[:4] == b[:4] or a[-4:] == b[-4:]:
            return difflib.SequenceMatcher(None, a, b).ratio() >= 0.86
    return False


def name_sim(ta, tb):
    """Similarity in [0,1] between two token lists (normalised, particles dropped).
    1.0 equal sets | 0.92 one name contained in the other (2+ tokens) | 0.8 two shared tokens
    0.7/0.55 a single shared token vs a mononym | 0.6 surname + same first initial."""
    if not ta or not tb:
        return 0.0
    A, B = list(dict.fromkeys(ta)), list(dict.fromkeys(tb))
    used_b = set()
    matched_a = set()
    for ia, a in enumerate(A):
        for jb, b in enumerate(B):
            if jb in used_b:
                continue
            if tok_eq(a, b):
                used_b.add(jb)
                matched_a.add(ia)
                break
    inter = len(matched_a)
    if inter == 0:
        return 0.0
    if inter == len(A) == len(B):
        return 1.0
    small = min(len(A), len(B))
    if inter == small:
        if small >= 2:
            return 0.92
        t = A[0] if len(A) == 1 else B[0]
        return 0.7 if len(t) >= 6 else 0.55
    if inter >= 2:
        return 0.8
    if len(A) >= 2 and len(B) >= 2:
        ra = {a[0] for i, a in enumerate(A) if i not in matched_a}
        rb = {b[0] for j, b in enumerate(B) if j not in used_b}
        if ra & rb:
            return 0.6
    return 0.0


def to_latin1(s):
    """Make sure a string can be written to the ISO-8859-1 CSV (transliterate the rest)."""
    out = []
    for ch in s:
        try:
            ch.encode("latin-1")
            out.append(ch)
        except UnicodeEncodeError:
            t = strip_accents(ch)
            out.append(t if t and all(ord(c) < 256 for c in t) else "?")
    return "".join(out)


# ----------------------------------------------------------------------------- raw CSV line handling
def split_raw(line):
    fields, start, in_q = [], 0, False
    for i, ch in enumerate(line):
        if ch == '"':
            in_q = not in_q
        elif ch == ";" and not in_q:
            fields.append(line[start:i])
            start = i + 1
    fields.append(line[start:])
    return fields


def unquote(raw):
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1].replace('""', '"')
    return raw


def encode_field(v):
    v = to_latin1(str(v))
    if ";" in v or '"' in v or "\r" in v or "\n" in v or v != v.strip():
        return '"' + v.replace('"', '""') + '"'
    return v


def reverter_nome(nome):
    """reverterNome() from script.js: 'Given Surname' -> 'Surname, Given'."""
    partes = nome.strip().split()
    if len(partes) < 2:
        return nome
    return f"{partes[-1]}, {' '.join(partes[:-1])}"


# ----------------------------------------------------------------------------- nationalities
# Transfermarkt (English) -> (ISO-ish code used by flags, Portuguese name as written in players.csv)
NATIONS = {
    "Albania": ("al", "Albânia"), "Algeria": ("dz", "Argélia"), "Angola": ("ao", "Angola"),
    "Argentina": ("ar", "Argentina"), "Armenia": ("am", "Arménia"), "Australia": ("au", "Austrália"),
    "Austria": ("at", "Áustria"), "Belarus": ("by", "Bielorrússia"), "Belgium": ("be", "Bélgica"),
    "Benin": ("bj", "Benim"), "Bosnia-Herzegovina": ("ba", "Bósnia"), "Brazil": ("br", "Brasil"),
    "Bulgaria": ("bg", "Bulgária"), "Burkina Faso": ("bf", "Burkina Fasso"), "Burundi": ("bi", "Burundi"),
    "Cameroon": ("cm", "Camarões"), "Canada": ("ca", "Canadá"), "Cape Verde": ("cv", "Cabo Verde"),
    "Central African Republic": ("cf", "Rep. Centro-Africana"), "Chile": ("cl", "Chile"), "China": ("cn", "China"),
    "Colombia": ("co", "Colômbia"), "Comoros": ("km", "Comores"), "Congo": ("cg", "Congo"),
    "Costa Rica": ("cr", "Costa Rica"), "Cote d'Ivoire": ("ci", "Costa do Marfim"), "Croatia": ("hr", "Croácia"),
    "Curacao": ("cw", "Curaçau"), "Cyprus": ("cy", "Chipre"), "Czech Republic": ("cz", "Chéquia"),
    "DR Congo": ("cd", "Rep. do Congo"), "Denmark": ("dk", "Dinamarca"), "Ecuador": ("ec", "Equador"),
    "Egypt": ("eg", "Egito"), "England": ("gb-eng", "Inglaterra"), "Equatorial Guinea": ("gq", "Guiné Equatorial"),
    "Estonia": ("ee", "Estónia"), "Faroe Islands": ("fo", "Ilhas Faroé"), "Finland": ("fi", "Finlândia"),
    "France": ("fr", "França"), "Gabon": ("ga", "Gabão"), "Georgia": ("ge", "Geórgia"), "Germany": ("de", "Alemanha"),
    "Ghana": ("gh", "Gana"), "Greece": ("gr", "Grécia"), "Guadeloupe": ("gp", "Guadalupe"), "Guinea": ("gn", "Guiné"),
    "Guinea-Bissau": ("gw", "Guiné-Bissau"), "Haiti": ("ht", "Haiti"), "Hungary": ("hu", "Hungria"),
    "Iceland": ("is", "Islândia"), "Indonesia": ("id", "Indonésia"), "Iran": ("ir", "Irão"), "Iraq": ("iq", "Iraque"),
    "Ireland": ("ie", "Irlanda"), "Israel": ("il", "Israel"), "Italy": ("it", "Itália"), "Jamaica": ("jm", "Jamaica"),
    "Japan": ("jp", "Japão"), "Jordan": ("jo", "Jordânia"), "Kenya": ("ke", "Quénia"),
    "Korea, South": ("kr", "Coreia do Sul"), "Kosovo": ("xk", "Kosovo"), "Latvia": ("lv", "Letónia"),
    "Libya": ("ly", "Líbia"), "Lithuania": ("lt", "Lituânia"), "Luxembourg": ("lu", "Luxemburgo"),
    "Madagascar": ("mg", "Madagáscar"), "Mali": ("ml", "Mali"), "Martinique": ("mq", "Ilhas Martinica"),
    "Mauritania": ("mr", "Mauritânia"), "Mexico": ("mx", "México"), "Moldova": ("md", "Moldávia"),
    "Montenegro": ("me", "Montenegro"), "Morocco": ("ma", "Marrocos"), "Mozambique": ("mz", "Moçambique"),
    "Netherlands": ("nl", "Países Baixos"), "New Zealand": ("nz", "Nova Zelândia"), "Niger": ("ne", "Níger"),
    "Nigeria": ("ng", "Nigéria"), "North Macedonia": ("mk", "Macedónia do Norte"),
    "Northern Ireland": ("gb-nir", "Irlanda do Norte"), "Norway": ("no", "Noruega"), "Panama": ("pa", "Panamá"),
    "Paraguay": ("py", "Paraguai"), "Poland": ("pl", "Polónia"), "Portugal": ("pt", "Portugal"),
    "Romania": ("ro", "Roménia"), "Russia": ("ru", "Rússia"), "Saudi Arabia": ("sa", "Arábia Saudita"),
    "Scotland": ("gb-sct", "Escócia"), "Senegal": ("sn", "Senegal"), "Serbia": ("rs", "Sérvia"),
    "Slovakia": ("sk", "Eslováquia"), "Slovenia": ("si", "Eslovénia"), "South Africa": ("za", "África do Sul"),
    "Spain": ("es", "Espanha"), "Suriname": ("sr", "Suriname"), "Sweden": ("se", "Suécia"),
    "Switzerland": ("ch", "Suíça"), "Syria": ("sy", "Síria"), "Tanzania": ("tz", "Tanzânia"),
    "The Gambia": ("gm", "Gâmbia"), "Togo": ("tg", "Togo"), "Tunisia": ("tn", "Tunísia"), "Türkiye": ("tr", "Turquia"),
    "Uganda": ("ug", "Uganda"), "Ukraine": ("ua", "Ucrânia"), "United States": ("us", "E.U.A."),
    "Uruguay": ("uy", "Uruguai"), "Uzbekistan": ("uz", "Uzbequistão"), "Venezuela": ("ve", "Venezuela"),
    "Wales": ("gb-wls", "País de Gales"), "Zambia": ("zm", "Zâmbia"), "Zimbabwe": ("zw", "Zimbabué"),
    # extra names that only show up as secondary flags
    "Peru": ("pe", "Perú"), "Bolivia": ("bo", "Bolívia"), "Cuba": ("cu", "Cuba"), "Honduras": ("hn", "Honduras"),
    "Dominican Republic": ("do", "República Dominicana"), "El Salvador": ("sv", "Salvador"),
    "Guatemala": ("gt", "Guatemala"), "Trinidad and Tobago": ("tt", "Trindade e Tobago"),
    "Lebanon": ("lb", "Líbano"), "Palestine": ("ps", "Palestina"), "Philippines": ("ph", "Filipinas"),
    "Malta": ("mt", "Malta"), "Rwanda": ("rw", "Ruanda"), "Ethiopia": ("et", "Etiópia"), "Sudan": ("sd", "Sudão"),
    "Sierra Leone": ("sl", "Serra Leoa"), "Liberia": ("lr", "Libéria"), "Kazakhstan": ("kz", "Cazaquistão"),
    "Azerbaijan": ("az", "Azerbaijão"), "Albania ": ("al", "Albânia"), "Malawi": ("mw", "Maláui"),
    "Namibia": ("na", "Namíbia"), "Botswana": ("bw", "Botsuana"), "Lesotho": ("ls", "Lesoto"),
    "Eritrea": ("er", "Eritreia"), "Chad": ("td", "Chade"), "Sao Tome and Principe": ("st", "S. Tomé e Príncipe"),
    "Korea, North": ("kp", "Coreia do Norte"), "Thailand": ("th", "Tailândia"), "Vietnam": ("vn", "Vietname"),
    "India": ("in", "Índia"), "Pakistan": ("pk", "Paquistão"), "Qatar": ("qa", "Qatar"),
    "United Arab Emirates": ("ae", "Emirados Árabes"), "Kuwait": ("kw", "Koweit"), "Oman": ("om", "Omã"),
    "Bahrain": ("bh", "Barém"), "Yemen": ("ye", "Iémen"), "Singapore": ("sg", "Singapura"),
    "Malaysia": ("my", "Malásia"), "Andorra": ("ad", "Andorra"), "Liechtenstein": ("li", "Liechtenstein"),
    "San Marino": ("sm", "São Marino"), "Gibraltar": ("gi", "Gibraltar"), "Fiji": ("fj", "Ilhas Fiji"),
}
ISO_TO_PT = {iso: pt for _en, (iso, pt) in NATIONS.items()}
PT_TO_ISO = {norm_text(pt): iso for iso, pt in ISO_TO_PT.items()}
PT_TO_ISO.update({norm_text("País Basco"): "es", norm_text("Rep. Dem. Congo"): "cd", norm_text("Burkina Faso"): "bf",
                  norm_text("Estados Unidos"): "us", norm_text("Curaçao"): "cw", norm_text("Zimbabwe"): "zw"})


def en_to_iso(name):
    n = NATIONS.get(name) or NATIONS.get((name or "").strip())
    return n[0] if n else None


def csv_nation_to_isos(nation):
    """players.csv 'Nation' ('Países Baixos / Gana', or an ISO code like 'de') -> set of codes."""
    out = set()
    for tok in (nation or "").split(" / "):
        t = tok.strip()
        if not t:
            continue
        if re.fullmatch(r"[a-z]{2}(-[a-z]{3})?", t):
            out.add(t)
        elif t.lower() == "cuba":
            out.add("cu")
        else:
            iso = PT_TO_ISO.get(norm_text(t))
            if iso:
                out.add(iso)
    return out


def ea_nat_to_iso(label):
    """EA nationality label (English) -> code, via the TM table with a few aliases."""
    aliases = {"Korea Republic": "kr", "Czechia": "cz", "Congo DR": "cd", "Gambia": "gm", "Ivory Coast": "ci",
               "Cote d'Ivoire": "ci", "Côte d'Ivoire": "ci", "China PR": "cn", "Republic of Ireland": "ie",
               "Bosnia and Herzegovina": "ba", "Cape Verde Islands": "cv", "Curaçao": "cw", "Türkiye": "tr",
               "Turkey": "tr", "USA": "us", "United States": "us", "Guinea Bissau": "gw", "Korea DPR": "kp",
               "FYR Macedonia": "mk", "North Macedonia": "mk", "Chinese Taipei": "tw", "Eswatini": "sz"}
    if label in aliases:
        return aliases[label]
    return en_to_iso(label)


# ----------------------------------------------------------------------------- positions
TM_GROUP = {
    "Goalkeeper": "G", "Centre-Back": "Z", "Left-Back": "L", "Right-Back": "L", "Defensive Midfield": "V",
    "Central Midfield": "M", "Attacking Midfield": "M", "Left Midfield": "PE", "Right Midfield": "PD",
    "Left Winger": "PE", "Right Winger": "PD", "Second Striker": "CA", "Centre-Forward": "CA",
    "Defender": "Z", "Midfielder": "M", "Striker": "CA", "Forward": "CA", "Attack": "CA",
}
TM_FM_POS = {
    "Goalkeeper": "GK", "Centre-Back": "D C", "Left-Back": "D L", "Right-Back": "D R", "Defensive Midfield": "DM",
    "Central Midfield": "M C", "Attacking Midfield": "AM C", "Left Midfield": "M L", "Right Midfield": "M R",
    "Left Winger": "AM L", "Right Winger": "AM R", "Second Striker": "AM C, ST", "Centre-Forward": "ST",
    "Defender": "D C", "Midfielder": "M C", "Striker": "ST", "Forward": "ST", "Attack": "ST",
}
EA_GROUP = {
    "GK": "G", "CB": "Z", "LB": "L", "RB": "L", "LWB": "L", "RWB": "L", "CDM": "V", "CM": "M", "CAM": "M",
    "LM": "PE", "RM": "PD", "LW": "PE", "RW": "PD", "CF": "CA", "ST": "CA",
}


def wing_foot(grp, foot):
    """Pé dos extremos no GoFoot: ponta esquerda (PE) joga com o pé esquerdo e ponta direita (PD) com o direito.
    Ambidestros (A) e as outras posições ficam como estão."""
    if grp == "PE" and foot == "D":
        return "E"
    if grp == "PD" and foot == "E":
        return "D"
    return foot


# ----------------------------------------------------------------------------- numeric utils
def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def isotonic(points):
    """Pool-adjacent-violators on [(x, y, w)] sorted by x -> list of (x, y) non-decreasing in y."""
    blocks = []  # [sum_w, sum_wy, n_points]
    for _x, y, w in points:
        blocks.append([w, y * w, 1])
        while len(blocks) > 1 and blocks[-2][1] / blocks[-2][0] > blocks[-1][1] / blocks[-1][0]:
            b = blocks.pop()
            blocks[-1][0] += b[0]
            blocks[-1][1] += b[1]
            blocks[-1][2] += b[2]
    res, i = [], 0
    for sw, swy, n in blocks:
        y = swy / sw
        for _ in range(n):
            res.append((points[i][0], y))
            i += 1
    return res


def interp(points, x, slope_lo=0.8, slope_hi=0.8):
    """Piece-wise linear interpolation with linear extrapolation outside the table."""
    if x <= points[0][0]:
        return points[0][1] + slope_lo * (x - points[0][0])
    if x >= points[-1][0]:
        return points[-1][1] + slope_hi * (x - points[-1][0])
    lo, hi = 0, len(points) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if points[mid][0] <= x:
            lo = mid
        else:
            hi = mid
    (x0, y0), (x1, y1) = points[lo], points[hi]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else y0


# ----------------------------------------------------------------------------- frontend/leagues.js
def load_leagues_js(path):
    """frontend/leagues.js (window.LEAGUES_DATA = {...};) -> dict pais -> liga -> [clubes]."""
    text = open(path, encoding="utf-8-sig").read()
    start = text.index("{", text.index("LEAGUES_DATA"))
    end = text.rindex("}")
    body = re.sub(r",(\s*[\]}])", r"\1", text[start:end + 1])  # trailing commas are legal JS, not JSON
    return json.loads(body)
