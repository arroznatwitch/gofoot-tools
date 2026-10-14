"""Gera o frontend/fm_players.js: os jogadores que o site carrega ao abrir, sem ser preciso importar o CSV.

Só entram os jogadores "completos", com a mesma regra que o site usa (marcarStatus em script.js): nome, nação,
clube (não livre), idade, pé, posição, atributos todos, TAL e valor de mercado. O resto da base continua a vir do
players.csv que se importa na aba Jogadores.

Também atualiza o selo "Última atualização" do frontend/index.html (usa --no-badge para não mexer nele).

Uso:
    python tools/build_site_data.py --csv players.csv
(escreve frontend/fm_players.js; volta a correr sempre que o players.csv mudar e faz commit dos dois ficheiros)
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gofoot_formulas as G  # noqa: E402
from common import CI, COLS, split_raw, unquote  # noqa: E402

PE = {"D": "Direito", "E": "Esquerdo", "A": "Ambidestro"}  # PE_LETRA_INVERSO em script.js
CAMPOS = ["id", "n", "nat", "c", "a", "p", "pe", "v", "sal", "tec", "ata", "def", "fis", "men", "ref", "pos_gk",
          "aer", "sai", "tal"]


def num_ou_none(s):
    """numOuNull() do importarCsv: vazio ou não numérico -> None."""
    s = (s or "").strip()
    if s == "":
        return None
    try:
        x = float(s)
    except ValueError:
        return None
    return int(x) if x == int(x) else x


def inverter_nome(nome):
    """inverterNome() do script.js: 'Apelido, Nome' -> 'Nome Apelido'."""
    if not nome or "," not in nome:
        return nome
    partes = [p.strip() for p in nome.split(",")]
    sobrenome, resto = partes[0], partes[1]
    return f"{resto} {sobrenome}" if (resto and sobrenome) else nome


def jogador_do_csv(f):
    """Campos do CSV -> objeto interno do site (o mesmo que importarCsv() monta)."""
    g = {c: unquote(f[CI[c]]) for c in COLS}
    m = re.match(r"\s*([+-]?\d+)", g["Age"])
    idade = int(m.group(1)) if m else None
    valor = num_ou_none(g["Valor"])
    return {
        "id": g["Id"],
        "n": inverter_nome(g["Name"]),
        "nat": g["Nation"] or "-",
        "c": g["Club"] if g["Club"] and g["Club"] != "-" else "-",
        "a": idade or None,
        "p": g["Posicao"] or g["Position"] or "",
        "pe": PE.get(g["Pe"], "-"),
        "v": valor if valor is not None else "-",
        "sal": num_ou_none(g["Salario"]),
        "tec": num_ou_none(g["TEC"]), "ata": num_ou_none(g["ATA"]), "def": num_ou_none(g["DEF"]),
        "fis": num_ou_none(g["FIS"]), "men": num_ou_none(g["MEN"]),
        "ref": num_ou_none(g["REF"]), "pos_gk": num_ou_none(g["POS_GK"]),
        "aer": num_ou_none(g["AER"]), "sai": num_ou_none(g["SAI"]),
        "tal": num_ou_none(g["TAL"]),
    }


def completo(j):
    """Mesma regra de marcarStatus() (j.completo), com a verdade/falsidade do JavaScript (0 e null são falsos)."""
    goleiro = G.posicao_grupo(j["p"]) == "G"
    atributos = (j["ref"] and j["pos_gk"] and j["aer"] and j["sai"] and j["men"]) if goleiro \
        else (j["tec"] and j["ata"] and j["def"] and j["fis"] and j["men"])
    valor_ok = isinstance(j["v"], (int, float)) and j["v"] > 0
    return bool(
        j["n"] and j["n"].strip() != ""
        and j["nat"] and j["nat"].strip() != "" and j["nat"] != "-"
        and j["c"] and j["c"].strip() != "" and j["c"] != "Sem clube" and j["c"] != "-"
        and j["a"]
        and j["pe"] and j["pe"] != "-"
        and j["p"] and j["p"].strip() != ""
        and atributos and j["tal"] and valor_ok
    )


def atualizar_selo(index_path, agora):
    texto = open(index_path, "rb").read().decode("utf-8")
    padrao = re.compile(r"(Ultima atualização: )\d{2}-\d{2}-\d{4} \d{1,2}:\d{2}")
    novo, n = padrao.subn(lambda m: m.group(1) + f"{agora:%d-%m-%Y} {agora.hour}:{agora.minute:02d}", texto)
    if n != 1:
        print("aviso: selo 'Ultima atualização' não encontrado em", index_path)
        return
    open(index_path, "wb").write(novo.encode("utf-8"))
    print(f"selo atualizado para {agora:%d-%m-%Y} {agora.hour}:{agora.minute:02d}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, help="players.csv")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "frontend", "fm_players.js"))
    ap.add_argument("--index", default=os.path.join(HERE, "..", "frontend", "index.html"))
    ap.add_argument("--no-badge", action="store_true", help="não atualizar o selo do index.html")
    ap.add_argument("--now", default=None, help="AAAA-MM-DDTHH:MM (por defeito, agora)")
    args = ap.parse_args()
    agora = datetime.datetime.fromisoformat(args.now) if args.now else datetime.datetime.now()

    raw = open(args.csv, "rb").read().decode("latin-1")
    linhas = raw.replace("\r\n", "\n").split("\n")
    assert split_raw(linhas[0]) == COLS, "cabeçalho inesperado no players.csv"
    total, escolhidos = 0, []
    for ln in linhas[1:]:
        if not ln:
            continue
        total += 1
        j = jogador_do_csv(split_raw(ln))
        if completo(j):
            escolhidos.append([j[c] for c in CAMPOS])

    corpo = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in escolhidos)
    js = (
        "// Gerado por tools/build_site_data.py a partir do players.csv. Não editar à mão.\n"
        f"// Jogadores completos que o site carrega ao abrir: {len(escolhidos)} de {total} ({agora:%d-%m-%Y %H:%M}).\n"
        "(function () {\n"
        f"    var campos = {json.dumps(CAMPOS)};\n"
        "    var linhas = [\n"
        f"{corpo}\n"
        "    ];\n"
        "    window.FM_PLAYERS_DATA = linhas.map(function (r) {\n"
        "        var o = {};\n"
        "        for (var i = 0; i < campos.length; i++) o[campos[i]] = r[i];\n"
        "        return o;\n"
        "    });\n"
        "})();\n"
    )
    out = os.path.abspath(args.out)
    with open(out, "wb") as f:
        f.write(js.encode("utf-8"))
    print(f"{len(escolhidos)} jogadores completos de {total} -> {out} ({len(js.encode('utf-8')) / 1048576:.2f} MB)")
    if not args.no_badge:
        atualizar_selo(os.path.abspath(args.index), agora)


if __name__ == "__main__":
    sys.exit(main())
