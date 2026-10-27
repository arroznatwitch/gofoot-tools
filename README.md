<p align="left">
  <img src="https://yt3.googleusercontent.com/_KRC6nzOghgWeL6rw3EDGdDweLrGMxyUSUzpFVW_Z_JvvoZalLMqgncRyaNtCVILvNYnNMn8=s900-c-k-c0x00ffffff-no-rj" width="120" alt="GoFoot Logo">
</p>

# GoFoot Tools

Ferramenta não-oficial para criar e organizar bases de jogadores para o jogo **GoFoot**. 

> ⚠️ Este projeto **não tem qualquer afiliação com o GoFoot**. É uma ferramenta feita de forma independente por fãs, apenas para ajudar a comunidade.

## O que faz

Abre um **patch** do GoFoot (pasta ou `.gdb`) no navegador, sem o alterar:

- **Clubes, Jogadores, Ligas**: vê e edita os dados numa cópia em memória
- **Elo**: ranking de força dos clubes com dados do [ClubElo](https://clubelo.com/Ranking); os clubes que lá não aparecem recebem uma estimativa pela divisão e reputação
- **Validar e exportar**: verifica o patch e gera um `.gdb` novo
- **Wiki**: explica o formato do patch, o Elo e como instalar

## Stack

HTML, CSS e JavaScript puro, mais [JSZip](https://stuk.github.io/jszip/) para ler e gerar `.gdb`.

## Elo (`tools/build_elo.py`)

Descarrega o CSV do ClubElo (`http://api.clubelo.com/AAAA-MM-DD`) e corre:

```
python tools/build_elo.py --ranking ranking.csv --patch "Documentos/Gofoot/Patches/portugal_2026"
```

Gera `frontend/elo.json`. Para os patches com jogadores (formato `teams.json`) corre depois `tools/build_elo_sim.py --legacy <patch> --patch-pt <portugal_2026>`, que simula o Elo dos clubes a partir da força dos plantéis, calibrado nos clubes portugueses, e gera `frontend/elo_sim.json`. Os restantes scripts em `tools/` são da base antiga em `players.csv` e já não alimentam o site.

## Apoiar o GoFoot

Se queres e gostas do jogo, considera apoiar diretamente:

- 💚 Apoia.se: [apoia.se/gofoot](https://apoia.se/gofoot)
- ☕ Ko-fi: [ko-fi.com/gofoot](https://ko-fi.com/gofoot)
- 🎮 Discord: [discord.gg/DAun2PRT8P](https://discord.gg/DAun2PRT8P)
- 📺 YouTube: [@Gofoot_game](https://www.youtube.com/@Gofoot_game)
- 📸 Instagram: [instagram.com/gofoot_game](https://instagram.com/gofoot_game)

---

<a href="https://ko-fi.com/gofoot" target="_blank">
  <img src="https://storage.ko-fi.com/cdn/brandasset/kofi_button_blue.png" height="55" alt="Support GoFoot on Ko-fi">
</a>
