"""Dá estádio aos clubes do patch portugal_2026 que não têm stadium_id.

Uso:
    python tools/fix_estadios.py --patch "…/portugal_2026" --out saida_estadios

O patch não é tocado: --out recebe data/stadiums.json e só os data/clubs/*.json que mudaram (mesmo formato do
original: tabs, chaves ordenadas, CRLF). Para aplicar, copiar a pasta data por cima da do patch.

- equipas B partilham o estádio da equipa principal (um estádio pode ser de vários clubes)
- Vitória FC e Beira-Mar têm o estádio real (Bonfim, Mário Duarte)
- os restantes ficam com "Estádio Municipal de <cidade>" (ou "Campo do <clube>" quando a cidade é incerta) e uma
  lotação estimada pela reputação do clube. São valores de partida: editar no editor do jogo se houver dados melhores.
"""
import argparse
import glob
import json
import os
import re
import unicodedata

# clube -> cidade (None = cidade incerta, o estádio leva o nome do clube e fica sem cidade)
CIDADE = {
    "pt_alcochetense": "Alcochete", "pt_alpendorada": "Alpendorada", "pt_amora": "Amora", "pt_benficacb": "Castelo Branco",
    "pt_braganca": "Bragança", "pt_brito": "Brito", "pt_calheta": "Calheta", "pt_camacha": "Camacha",
    "pt_castrodaire": "Castro Daire", "pt_celoricense": "Celorico de Basto", "pt_cinfaes": "Cinfães", "pt_elvas": "Elvas",
    "pt_fatima": "Fátima", "pt_fazendense": "Almeirim", "pt_flordagrade": None, "pt_florgrade": None,
    "pt_guarda": "Guarda", "pt_imortal": "Albufeira", "pt_juventudeevora": "Évora", "pt_lagoa": "Lagoa",
    "pt_lajense": None, "pt_limianos": "Ponte de Lima", "pt_machico": "Machico", "pt_maia": "Maia",
    "pt_malveira": "Malveira", "pt_mariadafonte": "Póvoa de Lanhoso", "pt_marialvas": "Marialva",
    "pt_mineiro": "Aljustrel", "pt_montalegre": "Montalegre", "pt_mortagua": "Mortágua", "pt_naval": "Figueira da Foz",
    "pt_nazarenos": "Nazaré", "pt_nogueirense": None, "pt_oliveirahospital": "Oliveira do Hospital",
    "pt_ovarense": "Ovar", "pt_pontedabarca": "Ponte da Barca", "pt_portel": "Portel", "pt_primeirodezembro": "Sintra",
    "pt_real": "Queluz", "pt_rebordosa": "Rebordosa", "pt_salgueiros": "Porto", "pt_sanjoanense": "São João da Madeira",
    "pt_serpa": "Serpa", "pt_sertanense": "Sertã", "pt_sintrense": "Sintra", "pt_sousense": None, "pt_tirsense": "Santo Tirso",
    "pt_uniaolamas": "Lamas", "pt_uniaoserra": None, "pt_vilamea": "Vila Meã", "pt_vinhais": "Vinhais",
}
EQUIPA_B = {"pt_alvercab": "pt_alverca", "pt_bragab": "pt_braga", "pt_chavesb": "pt_chaves", "pt_santaclarab": "pt_santaclara"}
REAIS = {"pt_vitoriasetubal": ("Estádio do Bonfim", "Setúbal", 18694), "pt_beiramar": ("Estádio Mário Duarte", "Aveiro", 9000)}
# reputação mínima -> lotação estimada
LOTACAO = [(28, 6000), (24, 4000), (22, 3000), (20, 2500), (18, 2000), (0, 1500)]


def slug(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower())


def dump(d):
    return json.dumps(d, ensure_ascii=False, indent="\t", sort_keys=True).replace("\n", "\r\n").encode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = os.path.join(a.patch, "data")
    estadios = json.load(open(os.path.join(data, "stadiums.json"), encoding="utf-8"))
    ids = {s["id"] for s in estadios["stadiums"]}
    clubes = {}
    for f in sorted(glob.glob(os.path.join(data, "clubs", "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        clubes[d["id"]] = d
    mudados, novos = [], []
    for cid, c in clubes.items():
        if c.get("stadium_id") in ids:
            continue
        if cid in EQUIPA_B:
            sid = clubes[EQUIPA_B[cid]]["stadium_id"]
        else:
            if cid in REAIS:
                nome, cidade, lot = REAIS[cid]
            else:
                cidade = CIDADE[cid]  # KeyError = clube novo sem entrada: acrescentar acima
                nome = f"Estádio Municipal de {cidade}" if cidade else f"Campo do {c['nome']}"
                lot = next(v for r, v in LOTACAO if c["reputacao"] >= r)
            sid = "pt_" + slug(nome)
            if sid in ids:  # dois clubes da mesma cidade partilham o estádio municipal
                pass
            else:
                est = {"id": sid, "nome": nome, "capacidade": lot}
                if cidade:
                    est["cidade"] = cidade
                estadios["stadiums"].append(est)
                ids.add(sid)
                novos.append(nome)
        c["stadium_id"] = sid
        mudados.append(cid)
    os.makedirs(os.path.join(a.out, "data", "clubs"), exist_ok=True)
    open(os.path.join(a.out, "data", "stadiums.json"), "wb").write(dump(estadios))
    for cid in mudados:
        open(os.path.join(a.out, "data", "clubs", cid + ".json"), "wb").write(dump(clubes[cid]))
    print(f"{len(mudados)} clubes com estádio novo, {len(novos)} estádios criados -> {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
