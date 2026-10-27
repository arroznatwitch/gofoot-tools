# Como este patch está organizado

Edite pelo editor do Gofoot ou direto nos arquivos. Ao voltar para o jogo, o editor recarrega o que mudou.

## Arquivos

| Caminho | O que é |
|---|---|
| `patch.json` | Nome, autor, versão e descrição do patch |
| `GUIA-IA.md` | Todos os campos de cada arquivo, com exemplo, para criar ou editar com IA |
| `schema/` | Os mesmos campos em JSON Schema |
| `data/countries.json` | Países |
| `data/clubs/{id}.json` | Um arquivo por clube: dados do clube, `jogadores`, `juniores` e `tecnico` |
| `data/coaches.json` | Técnicos sem clube |
| `data/stadiums.json` | Estádios (um estádio pode ser de vários clubes) |
| `data/competitions.json` | Ligas e copas, cada uma com os clubes inscritos em `teams` |
| `data/nationalities.json` | Opcional: nacionalidades novas (`code`, `name`); o mesmo código troca o nome de uma do jogo |
| `data/names/{código}.json` | Opcional: nomes para gerar jogadores daquela nacionalidade (no lugar dos do jogo) |

O patch guarda só a definição. Gols, jogos, energia e lesões pertencem à carreira e são ignorados aqui.

## Imagens (PNG)

| Pasta | Nome do arquivo | Tamanho |
|---|---|---|
| `images/clubs/` | `{id do clube}.png` | 256×256, fundo transparente |
| `images/competitions/` | o arquivo indicado em `logo_image` | 256×256 |
| `images/trophies/` | o arquivo indicado em `trophy_image` | 256×384 |
| `images/flags/` | `{código da nacionalidade}.png` (ou `{id do país}.png`) | 96×64 |
| `images/confederations/` | `{id da confederação}.png` | 256×256 |
| `images/stadiums/` | o arquivo indicado em `image` do estádio | 1280×720 |
| `images/cover.png` | capa do patch | 1280×720 |

Sem imagem, o jogo usa um escudo genérico nas cores do clube.

## Compartilhar

No editor, **Exportar** gera um `.gdb`: esta pasta compactada. Para instalar um patch, basta colar a pasta dele em `Documentos/Gofoot/Patches`. O nome da pasta usa só letras minúsculas, números, `_` e `-` (ex.: `liga_japonesa_2026`).