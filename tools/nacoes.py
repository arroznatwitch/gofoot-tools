"""Tabelas de nacionalidades: códigos ISO -> nome em português, grafias a normalizar e códigos para o site.

Os nomes são os do players.csv (grafia do FM, português de Portugal). O JSON do jogo, usado nas importações de
equipas, traz a nacionalidade como código ISO ("pt", "de", "gb-eng"...) ou como nome solto em minúsculas ("cuba",
"suiça", "eslovênia"), e isso entrou na coluna Nation de milhares de jogadores.
"""
import re


# Código ISO (como vem do JSON do jogo) -> nome canónico no players.csv.
# "en" e "sc" também aparecem no JSON do jogo, com o sentido de Inglaterra e Escócia.
CODE_TO_PT = {
    "ad": "Andorra", "ae": "Emirados Árabes", "al": "Albânia", "am": "Arménia", "ao": "Angola",
    "ar": "Argentina", "at": "Áustria", "au": "Austrália", "ba": "Bósnia", "be": "Bélgica",
    "bf": "Burkina Fasso", "bg": "Bulgária", "bi": "Burundi", "bj": "Benim", "bo": "Bolívia",
    "br": "Brasil", "by": "Bielorrússia", "ca": "Canadá", "cd": "Rep. do Congo", "cf": "Rep. Centro-Africana",
    "cg": "Congo", "ch": "Suíça", "ci": "Costa do Marfim", "cl": "Chile", "cm": "Camarões",
    "cn": "China", "co": "Colômbia", "cr": "Costa Rica", "cu": "Cuba", "cv": "Cabo Verde",
    "cw": "Curaçau", "cy": "Chipre", "cz": "Chéquia", "de": "Alemanha", "dk": "Dinamarca",
    "do": "República Dominicana", "dz": "Argélia", "ec": "Equador", "ee": "Estónia", "eg": "Egito",
    "en": "Inglaterra", "es": "Espanha", "fi": "Finlândia", "fo": "Ilhas Faroé", "fr": "França",
    "ga": "Gabão", "gb-eng": "Inglaterra", "gb-nir": "Irlanda do Norte", "gb-sct": "Escócia",
    "gb-wls": "País de Gales", "ge": "Geórgia", "gh": "Gana", "gm": "Gâmbia", "gn": "Guiné",
    "gq": "Guiné Equatorial", "gr": "Grécia", "gw": "Guiné-Bissau", "hn": "Honduras", "hr": "Croácia",
    "ht": "Haiti", "hu": "Hungria", "id": "Indonésia", "ie": "Irlanda", "il": "Israel",
    "iq": "Iraque", "ir": "Irão", "is": "Islândia", "it": "Itália", "jm": "Jamaica",
    "jp": "Japão", "ke": "Quénia", "km": "Comores", "kr": "Coreia do Sul", "lc": "St Lucia",
    "li": "Liechtenstein", "lt": "Lituânia", "lu": "Luxemburgo", "lv": "Letónia", "ma": "Marrocos",
    "md": "Moldávia", "me": "Montenegro", "mk": "Macedónia do Norte", "ml": "Mali", "mq": "Ilhas Martinica",
    "mr": "Mauritânia", "mt": "Malta", "mx": "México", "mz": "Moçambique", "ng": "Nigéria",
    "nl": "Países Baixos", "no": "Noruega", "nz": "Nova Zelândia", "pa": "Panamá", "pe": "Perú",
    "pk": "Paquistão", "pl": "Polónia", "ps": "Palestina", "pt": "Portugal", "py": "Paraguai",
    "ro": "Roménia", "rs": "Sérvia", "ru": "Rússia", "sc": "Escócia", "se": "Suécia",
    "si": "Eslovénia", "sk": "Eslováquia", "sl": "Serra Leoa", "sm": "São Marino", "sn": "Senegal",
    "sr": "Suriname", "tn": "Tunísia", "th": "Tailândia", "tr": "Turquia", "tt": "Trindade e Tobago",
    "ua": "Ucrânia", "us": "E.U.A.", "uy": "Uruguai", "ve": "Venezuela", "xk": "Kosovo",
    "za": "África do Sul", "zm": "Zâmbia", "sy": "Síria",
}

# Outras grafias (em minúsculas) -> nome canónico. Inclui nomes em português do Brasil e variantes raras.
NATION_FIXES = {
    "cuba": "Cuba", "suiça": "Suíça", "bósnia-herzegovina": "Bósnia", "hong kong": "Hong Kong (RP China)",
    "cabo verde": "Cabo Verde", "bielorrússia": "Bielorrússia", "síria": "Síria", "cazaquistão": "Cazaquistão",
    "eslovênia": "Eslovénia", "romênia": "Roménia", "são marinho": "São Marino", "haiti": "Haiti",
    "malta": "Malta", "el salvador": "Salvador", "armênia": "Arménia",
    "república democrática do congo": "Rep. do Congo", "rd do congo": "Rep. do Congo", "rd congo": "Rep. do Congo",
    "república do congo": "Congo", "gâmbia": "Gâmbia", "líbia": "Líbia", "palestina": "Palestina",
    "sudão do sul": "Sudão do Sul", "vanuatu": "Vanuatu", "vietname": "Vietname", "tajiquistão": "Tajiquistão",
    "níger": "Níger", "turquemenistão": "Turcomenistão", "trinidad": "Trindade e Tobago",
    "trinidade e tobago": "Trindade e Tobago", "egipto": "Egito", "madagascar": "Madagáscar",
    "chinese taipei": "Taipé (RP China)", "macedônia do norte": "Macedónia do Norte", "malawi": "Maláui",
    "rep. dominicana": "República Dominicana", "san marino": "São Marino",
}

# Nomes do players.csv que o ISO_NACOES do frontend/script.js ainda não conhecia -> código ISO.
# Servem para o botão Exportar dar sempre o código ISO em "nacionalidade".
SITE_ISO_ADDITIONS = {
    "Andorra": "ad", "Anguilha": "ai", "Antígua e Barbuda": "ag", "Aruba": "aw", "Bahamas": "bs",
    "Bangladexe": "bd", "Barbados": "bb", "Barém": "bh", "Belize": "bz", "Benim": "bj",
    "Bermudas": "bm", "Bielorrússia": "by", "Bonaire": "bq", "Botsuana": "bw", "Brunei": "bn",
    "Burkina Fasso": "bf", "Burundi": "bi", "Butão": "bt", "Cabo Verde": "cv", "Camboja": "kh",
    "Cazaquistão": "kz", "Chade": "td", "Comores": "km", "Congo": "cg", "Coreia do Norte": "kp",
    "Curaçau": "cw", "Djibuti": "dj", "Dominica": "dm", "E.U.A.": "us", "Emirados Árabes": "ae",
    "Eritreia": "er", "Essuatíni": "sz", "Etiópia": "et", "Filipinas": "ph", "Gibraltar": "gi",
    "Granada": "gd", "Guadalupe": "gp", "Guam": "gu", "Guatemala": "gt", "Guiana": "gy",
    "Guiana Francesa": "gf", "Guiné Equatorial": "gq", "Guiné-Bissau": "gw", "Gâmbia": "gm", "Haiti": "ht",
    "Hong Kong (RP China)": "hk", "Ilhas Caimão": "ky", "Ilhas Cook": "ck", "Ilhas Fiji": "fj",
    "Ilhas Martinica": "mq", "Ilhas Reunião": "re", "Ilhas Salomão": "sb", "Ilhas T & C": "tc",
    "Ilhas Virgens (EUA)": "vi", "Ilhas Virgens (RU)": "vg", "Ilhas Wallis e Futuna": "wf", "Iémen": "ye",
    "Jordânia": "jo", "Koweit": "kw", "Laos": "la", "Lesoto": "ls", "Libéria": "lr",
    "Liechtenstein": "li", "Líbano": "lb", "Líbia": "ly", "Macau (RP China)": "mo", "Madagáscar": "mg",
    "Maiote": "yt", "Maldivas": "mv", "Malta": "mt", "Maláui": "mw", "Marianas do Norte": "mp",
    "Mauritânia": "mr", "Maurícia": "mu", "Mianmar": "mm", "Micronésia": "fm", "Moldávia": "md",
    "Mongólia": "mn", "Monserrate": "ms", "Moçambique": "mz", "Mónaco": "mc", "Namíbia": "na",
    "Nepal": "np", "Nicarágua": "ni", "Nova Caledónia": "nc", "Níger": "ne", "Omã": "om",
    "Palestina": "ps", "Papua-Nova Guiné": "pg", "Paquistão": "pk", "País Basco": "es", "Porto Rico": "pr",
    "Quirguistão": "kg", "Rep. Centro-Africana": "cf", "Rep. do Congo": "cd", "República Dominicana": "do",
    "Ruanda": "rw", "S. Tomé e Príncipe": "st", "S. Vincente": "vc", "Salvador": "sv",
    "Samoa Americana": "as", "Samoa Ocidental": "ws", "Seicheles": "sc", "Seri Lanca": "lk",
    "Singapura": "sg", "Somália": "so", "St Lucia": "lc", "Sudão": "sd", "Sudão do Sul": "ss",
    "Suriname": "sr", "São Bartolomeu": "bl", "São Cristóvão e Neves": "kn", "São Marino": "sm",
    "São Martinho": "sx", "Síria": "sy", "Taipé (RP China)": "tw", "Taiti": "pf", "Tajiquistão": "tj",
    "Tanzânia": "tz", "Timor-Leste": "tl", "Togo": "tg", "Tonga": "to", "Trindade e Tobago": "tt",
    "Turcomenistão": "tm", "Tuvalu": "tv", "Uganda": "ug", "Vanuatu": "vu", "Vietname": "vn",
    "Zanzibar": "tz", "Zimbabué": "zw",
}


_VARIANTES_COM_MAIUSCULA = {"el salvador", "rd congo", "rep. dominicana", "san marino", "trinidade e tobago"}


def normalizar_nacao(token):
    """Um código ou nome solto de nacionalidade -> nome canónico em português.
    Se já for um nome certo devolve o próprio texto."""
    t = token.strip()
    if not t:
        return token
    low = t.lower()
    if re.fullmatch(r"[A-Za-z]{2}(-[A-Za-z]{3})?", t) and low in CODE_TO_PT:
        return CODE_TO_PT[low]
    if low in NATION_FIXES and (not t[0].isupper() or low in _VARIANTES_COM_MAIUSCULA):
        return NATION_FIXES[low]
    return token
