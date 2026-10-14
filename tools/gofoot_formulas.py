"""Port em Python das fórmulas do site GoFoot Tools (frontend/script.js).

Tudo aqui espelha o JavaScript para que os valores escritos no players.csv sejam
exatamente os que o site calcularia: posicaoGrupo, calcularOverallDinamico,
calcularValorMercado, calcularSalario.
"""
import math

GRUPOS_VALIDOS = ["G", "Z", "L", "V", "M", "PD", "PE", "CA"]

OVER_WEIGHTS = {
    "G":  {"REF": 0.20, "POS": 0.20, "AER": 0.20, "SAI": 0.20, "MEN": 0.20},
    "Z":  {"TEC": 0.15, "ATA": 0.05, "DEF": 0.40, "FIS": 0.25, "MEN": 0.15},
    "L":  {"TEC": 0.25, "ATA": 0.05, "DEF": 0.35, "FIS": 0.20, "MEN": 0.15},
    "V":  {"TEC": 0.25, "ATA": 0.05, "DEF": 0.35, "FIS": 0.20, "MEN": 0.15},
    "M":  {"TEC": 0.35, "ATA": 0.30, "DEF": 0.05, "FIS": 0.10, "MEN": 0.20},
    "PD": {"TEC": 0.25, "ATA": 0.40, "DEF": 0.05, "FIS": 0.15, "MEN": 0.15},
    "PE": {"TEC": 0.25, "ATA": 0.40, "DEF": 0.05, "FIS": 0.15, "MEN": 0.15},
    "CA": {"TEC": 0.20, "ATA": 0.40, "DEF": 0.05, "FIS": 0.20, "MEN": 0.15},
}

_EA_MAP = {
    "GK": "G", "CB": "Z",
    "LB": "L", "RB": "L", "LWB": "L", "RWB": "L",
    "CDM": "V",
    "CM": "M", "LM": "M", "RM": "M", "CAM": "M",
    "LW": "PE", "RW": "PD",
    "CF": "CA", "ST": "CA",
}


def js_round(x):
    """Math.round: halves round towards +infinity."""
    return math.floor(x + 0.5)


def posicao_grupo(p):
    primeira = (p or "").split(",")[0].strip().upper()
    if not primeira:
        return None
    if primeira in GRUPOS_VALIDOS:
        return primeira
    if primeira in _EA_MAP:
        return _EA_MAP[primeira]
    if primeira.startswith("GK") or primeira.startswith("GR"):
        return "G"
    if primeira.startswith("DM"):
        return "V"
    if primeira.startswith("WB"):
        return "L"
    if primeira.startswith("D"):
        if "L" in primeira or "R" in primeira:
            return "L"
        return "Z"
    if primeira.startswith("AM"):
        if "L" in primeira:
            return "PE"
        if "R" in primeira:
            return "PD"
        return "M"
    if primeira.startswith("M"):
        return "M"
    if primeira.startswith("ST") or primeira.startswith("FW") or primeira.startswith("CF"):
        return "CA"
    return None


def attr_keys(grupo):
    """Attribute names (CSV column names) used by the OVER formula of a group."""
    return list(OVER_WEIGHTS[grupo].keys())


def calcular_over(grupo, attrs):
    """attrs: dict with TEC/ATA/DEF/FIS/MEN (or REF/POS/AER/SAI/MEN). None if incomplete."""
    pesos = OVER_WEIGHTS.get(grupo)
    if not pesos:
        return None
    total = 0.0
    for k, w in pesos.items():
        v = attrs.get(k)
        if v is None or v == "":
            return None
        total += float(v) * w
    return js_round(total)


def calcular_valor(grupo, over, tal, idade, fis=None, men=None):
    if over is None or tal is None or idade is None:
        return None
    if idade <= 19:
        tal_n = max(0.01, (tal - 30) / 70)
        ovr_n = max(0.01, (over - 30) / 70)
        valor_base = 20000 + 600000000 * math.pow(tal_n, 5.5) * math.pow(ovr_n, 1.5)
        fator_idade = 1 + (19 - idade) * 0.06
    elif idade <= 33:
        valor_base = 800000 * math.exp(0.10 * (over - 50) + 0.042 * (tal - 50))
        fator_idade = 1 if idade <= 26 else 1 - (idade - 26) * 0.08
    else:
        fis_raw = men if grupo == "G" else fis
        fisico = float(fis_raw) if fis_raw is not None else over
        valor_base = 5000000 * math.exp(0.025 * (over - 50) + 0.010 * (fisico - 50))
        fator_idade = 0.40 * math.pow(0.72, idade - 34)
    h = over * 7919 + idade * 6271 + tal * 3571
    noise = 0.95 + ((abs(h) % 1000) / 1000) * 0.10
    fator_pos = 0.60 if grupo == "G" else 1
    valor_final = valor_base * fator_idade * fator_pos * noise
    if valor_final < 5000:
        valor_final = 5000
    return js_round(valor_final)


def calcular_salario(over, valor):
    if over is None or valor is None or valor <= 0:
        return None
    if over > 90:
        mult = 1.75
    elif over >= 80:
        mult = 1.50
    elif over >= 75:
        mult = 1.25
    else:
        mult = 1.00
    return js_round(valor * 0.001 * mult)
