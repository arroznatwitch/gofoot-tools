# tools/ — adicionar ligas novas ao GoFoot Tools

Scripts em Python 3 (testados com 3.14, **sem bibliotecas externas**) que foram usados para acrescentar Inglaterra,
França, Itália, Holanda, Bélgica e Áustria. Servem para repetir o processo com outras ligas.

O que fazem, em resumo: descarregam os plantéis atuais do Transfermarkt e os ratings da EA FC, ligam cada jogador à
linha dele no `players.csv` (export do FM) e **só preenchem quem ainda não tem OVER**: OVER, TAL, atributos, pé,
posição, valor e salário. Quem já tinha OVER nunca é alterado.

## Passo a passo

Na raiz do repositório (a pasta `tools/work/` está no `.gitignore`):

```bash
# 1. ratings da EA FC (~16 mil jogadores, 1-2 min)
python tools/fetch_ea.py --out tools/work/ea_all.json

# 2. clubes e plantéis do Transfermarkt (as ligas vêm do config.json; faz pausas, guarda cache)
python tools/fetch_transfermarkt.py --out tools/work/tm_squads.json --cache-dir tools/work/tm_raw

# 3. construir o novo players.csv (não toca no original). --diag mostra os casos duvidosos
python tools/build_leagues.py --csv players.csv --ea tools/work/ea_all.json --tm tools/work/tm_squads.json --out tools/work/out --diag

# 4. verificar (tem de passar tudo)
python tools/verify_build.py --orig players.csv --new tools/work/out/players_new.csv --leagues-add tools/work/out/leagues_add.json

# 5. aplicar: substituir o CSV e acrescentar as ligas ao site
cp tools/work/out/players_new.csv players.csv
python tools/update_leagues_js.py --add tools/work/out/leagues_add.json --before Suécia
```

Depois importa o `players.csv` no site e confirma na aba **Ligas** (cada clube novo deve ter 20+ completos).

Outros scripts: `test_formulas.py` confirma que o port das fórmulas do site (`gofoot_formulas.py`) reproduz o CSV
(Valor e Salário a 100%). `common.py` tem as funções de apoio (nomes, nacionalidades, leitura do `leagues.js`).

## Para outras ligas

Edita o `config.json`:

* `leagues`: país (como aparece no site), nome da liga, `site_label` (ex.: `"Premier League - 26/27"`) e o `tm_slug` /
  `tm_code` que aparecem no URL da liga no Transfermarkt (`.../premier-league/startseite/wettbewerb/GB1`).
* `club_name_variants`: **confirma antes no CSV** como se chamam os clubes. Os jogadores já avaliados que mudaram de
  clube em transferências usam o nome do Transfermarkt, às vezes abreviado (`Juventus`, `Fulham`, `Leeds`). Se o nome
  do clube no `leagues.js` for diferente, esses jogadores deixam de contar para o clube. Indica aqui as grafias a usar.
* `tal_ref_cap` e `tal_pins`: referências de TAL do jogo (máximo por posição e jogadores conhecidos).

## Como são calculados os valores

* **OVER com rating da EA** (a maioria): a escala do GoFoot é praticamente a da EA (nas linhas feitas à mão, os
  quantis de La Liga coincidem). `OVER = EA − clamp((EA−76)/5, 0, 1.5) + clamp((26−idade)×0,15, −1,6, +1)`.
* **OVER só com FM**: o rating do FM passa pela conversão FM→GoFoot recuperada das linhas que o commit `855cdaa`
  gerou, mais uma correção por liga e idade medida contra a EA (o FM sobrestima jovens e a liga austríaca).
* **OVER só com o valor do Transfermarkt**: mediana do OVER de jogadores da EA com valor e idade parecidos; jovens
  até 19 anos levam um desconto, porque o valor deles é sobretudo potencial.
* **TAL**: diferença entre potencial e rating do FM somada ao novo OVER (ou a diferença TAL−OVER habitual por posição
  e idade, medida no CSV). Limitado pelas referências por posição para 22+ anos.
* **Atributos**: regressão (ridge) por posição dos stats da EA, treinada nas linhas já avaliadas; desloca-se tudo para
  que a fórmula do site dê exatamente o OVER. Sem EA usa-se o perfil de um jogador parecido já avaliado.
* **Valor e Salário**: as fórmulas do `script.js`.
* Idade, clube e nacionalidade principal vêm do Transfermarkt; nomes estragados pelo export do FM (`Joako` por `Josko`)
  são repostos.

## Formato do `players.csv` (cuidados)

`;` como separador, ISO-8859-1, 32 colunas, **sem newline no fim**. Na pasta de trabalho tem CRLF; o git guarda-o com
LF (`core.autocrlf`). Por isso o build edita as linhas "cruas": as que não muda ficam byte a byte iguais. Caracteres
fora de ISO-8859-1 são transliterados (`š` → `s`). Os scripts usam `--today` (data para as idades) e `--seed` (Ids
novos) para poderem ser repetidos com o mesmo resultado.

## Limitações conhecidas

* O FM troca alguns caracteres (`Joško` → `Joako`); a ligação é feita com tolerância a uma letra, data de nascimento,
  nacionalidade e clube. Casos raros podem ficar sem ligação: nesse caso o jogador entra como linha nova.
* Jogadores já avaliados que o Transfermarkt coloca num clube novo mas que no CSV estão noutro clube (ou livres) não
  são mexidos; ficam listados em `report.json` (`rated_in_other_club`).
* Ficam jogadores do FM **sem OVER** nos clubes (reservas, antigos). Usa o "Limpar sem OVER" do Painel++.
* Nacionalidades que o `ISO_NACOES` do `script.js` não conhece (E.U.A., Rep. do Congo, Cabo Verde...) exportam-se sem
  código ISO. Já acontecia antes.
* A calibração usa o commit `855cdaa` do git. Num clone raso, usa `--pre` com um snapshot do `players.csv` anterior a ele.

## Primeira execução (14-10-2026)

106 clubes (Premier League, Ligue 1, Serie A, Eredivisie, Jupiler Pro League, Bundesliga austríaca), 2 970 jogadores no
Transfermarkt: 2 796 linhas do FM completadas + 59 jogadores novos. OVER pela EA (~2 150), pelo FM (~670) e só por valor
de mercado (37). 0 linhas com OVER alteradas.

Dados de terceiros (EA, Transfermarkt): usa com moderação, não aceleres os pedidos e não faças commit de `tools/work/`.
