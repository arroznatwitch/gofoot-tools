"""Põe o nome (em português) em todas as nacionalidades do players.csv que estão como código ISO ("pt", "de",
"gb-eng"...) ou como nome solto em minúsculas ("cuba", "suiça"), e confirma que o site sabe converter cada nome
de volta em código ISO na hora de exportar.

Só muda a coluna Nation; todas as outras colunas e linhas ficam byte a byte iguais.

Uso:
    python tools/fix_nationalities.py --csv players.csv --out tools/work/players_nacoes.csv
    python tools/fix_nationalities.py --csv players.csv --in-place
    python tools/fix_nationalities.py --csv players.csv --check     (só lista o que o site não converte em ISO)
"""
import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import CI, COLS, encode_field, split_raw, unquote  # noqa: E402
from nacoes import normalizar_nacao  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def ler_iso_do_site(script_js):
    """O dicionário ISO_NACOES do frontend/script.js: nome em minúsculas -> código."""
    texto = open(script_js, encoding="utf-8").read()
    m = re.search(r"const ISO_NACOES = \{(.*?)\n\};", texto, re.S)
    if not m:
        raise SystemExit("não encontrei ISO_NACOES em " + script_js)
    return dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', m.group(1))), "const inteiro = nat.trim().toLowerCase();" in texto


def resolver_como_o_site(nat, iso, procura_inteira):
    """resolverNacaoISO() do script.js. Devolve (código, reconhecido)."""
    if not nat or nat == "-":
        return None, False
    if procura_inteira and nat.strip().lower() in iso:
        return iso[nat.strip().lower()], True
    partes = [p.strip().lower() for p in re.split(r"\s*/\s*|\s+e\s+|,\s*", nat, flags=re.I) if p.strip()]
    for p in partes:
        if p in iso:
            return iso[p], True
    return (partes[0] if partes else None), False


def ler(csv_path):
    raw = open(csv_path, "rb").read().decode("latin-1")
    nl = "\r\n" if "\r\n" in raw else "\n"
    termina = raw.endswith(nl)
    linhas = raw.split(nl)
    if termina:
        linhas.pop()
    assert split_raw(linhas[0]) == COLS, "cabeçalho inesperado"
    return linhas, nl, termina


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", help="ficheiro de saída")
    ap.add_argument("--in-place", action="store_true", help="escrever por cima do --csv")
    ap.add_argument("--check", action="store_true", help="só verificar, não escreve nada")
    ap.add_argument("--script-js", default=os.path.join(HERE, "..", "frontend", "script.js"))
    args = ap.parse_args()
    if not (args.check or args.out or args.in_place):
        ap.error("indica --out, --in-place ou --check")

    linhas, nl, termina = ler(args.csv)
    conversoes = collections.Counter()
    por_converter = collections.Counter()
    saida = [linhas[0]]
    alteradas = 0
    for ln in linhas[1:]:
        f = split_raw(ln)
        nat = unquote(f[CI["Nation"]])
        tokens = nat.split(" / ")
        novos = [normalizar_nacao(t) for t in tokens]
        for velho, novo in zip(tokens, novos):
            if velho != novo:
                conversoes[(velho, novo)] += 1
            elif novo and not novo[0].isupper():
                por_converter[novo] += 1
        nova_nat = " / ".join(novos)
        if nova_nat != nat:
            f2 = list(f)
            f2[CI["Nation"]] = encode_field(nova_nat)
            nova = ";".join(f2)
            assert all(a == b for k, (a, b) in enumerate(zip(split_raw(nova), f)) if k != CI["Nation"])
            ln = nova
            alteradas += 1
        saida.append(ln)

    print(f"linhas: {len(linhas) - 1} | com nacionalidade corrigida: {alteradas}")
    if conversoes:
        print("conversões mais frequentes:")
        for (a, b), n in conversoes.most_common(15):
            print(f"   {a!r:34} -> {b!r:26} {n}")
        print(f"   ... {len(conversoes)} conversões diferentes")
    if por_converter:
        print("AINDA SEM NOME (não sei converter):", dict(por_converter))

    # o site consegue voltar a transformar cada nome em código ISO?
    iso, procura_inteira = ler_iso_do_site(args.script_js)
    sem_iso = collections.Counter()
    for ln in saida[1:]:
        nat = unquote(split_raw(ln)[CI["Nation"]])
        codigo, ok = resolver_como_o_site(nat, iso, procura_inteira)
        if not ok:
            sem_iso[nat] += 1
    print("resolverNacaoISO() com procura do nome inteiro:", "sim" if procura_inteira else "NÃO (nomes com ' e ' falham)")
    print(f"nomes que o site não converte em ISO: {len(sem_iso)} ({sum(sem_iso.values())} linhas)")
    if sem_iso:
        print("   ", dict(sem_iso.most_common(20)))

    if args.check:
        return 1 if (por_converter or sem_iso or alteradas) else 0
    if por_converter:
        raise SystemExit("há nacionalidades por converter; acrescenta-as a tools/nacoes.py")
    destino = args.csv if args.in_place else args.out
    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    with open(destino, "wb") as fh:
        fh.write((nl.join(saida) + (nl if termina else "")).encode("latin-1"))
    print("escrito:", destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
