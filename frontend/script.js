// Nomes de nação (inglês, usado nos CSVs, e português, usado no formulário) -> código ISO2.
// Usado só na exportação, para preencher "nacionalidade" no formato que o GoFoot espera.
const ISO_NACOES = {
    "argentina":"ar","armenia":"am","arménia":"am","australia":"au","austrália":"au","austria":"at","áustria":"at",
    "belgium":"be","bélgica":"be","bolivia":"bo","bolívia":"bo","bosnia and herzegovina":"ba","bósnia":"ba",
    "brazil":"br","brasil":"br","bulgaria":"bg","bulgária":"bg","cameroon":"cm","camarões":"cm","canada":"ca","canadá":"ca",
    "chile":"cl","china":"cn","china pr":"cn","colombia":"co","colômbia":"co","costa rica":"cr","cuba":"cu",
    "san marino":"sm",
    "croatia":"hr","croácia":"hr","cyprus":"cy","chipre":"cy","czechia":"cz","czech republic":"cz","chéquia":"cz","república checa":"cz",
    "denmark":"dk","dinamarca":"dk","ecuador":"ec","equador":"ec","egypt":"eg","egito":"eg",
    "england":"gb-eng","inglaterra":"gb-eng","estonia":"ee","estónia":"ee",
    "finland":"fi","finlândia":"fi","faroe islands":"fo","ilhas faroé":"fo","france":"fr","frança":"fr",
    "georgia":"ge","geórgia":"ge","germany":"de","alemanha":"de","ghana":"gh","gana":"gh",
    "greece":"gr","grécia":"gr","guinea":"gn","guiné":"gn","honduras":"hn","hungary":"hu","hungria":"hu",
    "iceland":"is","islândia":"is","india":"in","índia":"in","indonesia":"id","indonésia":"id",
    "iran":"ir","irão":"ir","iraq":"iq","iraque":"iq","republic of ireland":"ie","irlanda":"ie","israel":"il","italy":"it","itália":"it",
    "cote d'ivoire":"ci","ivory coast":"ci","costa do marfim":"ci","jamaica":"jm","japan":"jp","japão":"jp",
    "kenya":"ke","quénia":"ke","kosovo":"xk","latvia":"lv","letónia":"lv","lithuania":"lt","lituânia":"lt",
    "luxembourg":"lu","luxemburgo":"lu","malaysia":"my","malásia":"my","mali":"ml","mexico":"mx","méxico":"mx",
    "montenegro":"me","morocco":"ma","marrocos":"ma","netherlands":"nl","holanda":"nl","países baixos":"nl",
    "new zealand":"nz","nova zelândia":"nz","nigeria":"ng","nigéria":"ng","north macedonia":"mk","macedónia do norte":"mk",
    "northern ireland":"gb-nir","irlanda do norte":"gb-nir","norway":"no","noruega":"no",
    "panama":"pa","panamá":"pa","paraguay":"py","paraguai":"py","peru":"pe","perú":"pe",
    "poland":"pl","polónia":"pl","portugal":"pt","qatar":"qa","romania":"ro","roménia":"ro","russia":"ru","rússia":"ru",
    "saudi arabia":"sa","arábia saudita":"sa","scotland":"gb-sct","escócia":"gb-sct",
    "senegal":"sn","serbia":"rs","sérvia":"rs","slovakia":"sk","eslováquia":"sk","slovenia":"si","eslovénia":"si",
    "south africa":"za","áfrica do sul":"za","korea republic":"kr","south korea":"kr","coreia do sul":"kr",
    "spain":"es","espanha":"es","sweden":"se","suécia":"se","switzerland":"ch","suíça":"ch",
    "thailand":"th","tailândia":"th","tunisia":"tn","tunísia":"tn","turkiye":"tr","turkey":"tr","turquia":"tr",
    "ukraine":"ua","ucrânia":"ua","united arab emirates":"ae","emirados árabes unidos":"ae",
    "united states":"us","estados unidos":"us","uruguay":"uy","uruguai":"uy","uzbekistan":"uz","uzbequistão":"uz",
    "venezuela":"ve","wales":"gb-wls","gales":"gb-wls","país de gales":"gb-wls","algeria":"dz","argélia":"dz","angola":"ao","albania":"al","albânia":"al",
    "afghanistan":"af","afeganistão":"af","azerbaijan":"az","azerbaijão":"az","sierra leone":"sl","serra leoa":"sl",
    "burkina faso":"bf","gabon":"ga","gabão":"ga","zambia":"zm","zâmbia":"zm","zimbabwe":"zw","curacao":"cw","curaçao":"cw",
};

// Alguns jogadores têm dupla nacionalidade no CSV (ex: "Ilhas Faroé / Dinamarca").
// Como o dicionário só tem nomes únicos, isto separa por "/" (ou outros
// separadores comuns) e tenta cada parte, ficando com a primeira que bater certo.
function resolverNacaoISO(nat) {
    if (!nat || nat === "-") return null;
    const partes = nat.split(/\s*\/\s*|\s+e\s+|,\s*/i).map(p => p.trim().toLowerCase()).filter(Boolean);
    for (const parte of partes) {
        if (ISO_NACOES[parte]) return ISO_NACOES[parte];
    }
    // nenhuma parte reconhecida: devolve o texto original (primeira parte) em minúsculas, em vez de null
    return partes[0] || null;
}

// ID estável e ÚNICO do jogador: gerado UMA vez (na primeira importação/criação)
// e depois preservado em todas as exportações/reimportações seguintes — é o que
// permite juntar o envio de uma equipa de volta ao ficheiro mestre, sabendo
// exactamente qual jogador é qual.
//
// O sufixo é ALEATÓRIO (não um contador por sessão). O contador reiniciava a cada
// ficheiro/sessão, por isso dois homónimos exportados em ficheiros diferentes
// recebiam o mesmo "nome_0000001" e colidiam. Com um sufixo aleatório o ID é
// globalmente único mesmo para jogadores com o mesmo nome.
const idsEmitidos = new Set();
function gerarIdJogador(nome) {
    const slug = (nome || "jogador")
        .normalize("NFD").replace(/[̀-ͯ]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "");
    let id;
    do {
        const aleatorio = Math.random().toString(36).slice(2, 10); // 8 chars base36
        id = slug + "_" + aleatorio;
    } while (idsEmitidos.has(id));
    idsEmitidos.add(id);
    return id;
}

// Gera um Id único que também não colide com nenhum Id já registado no mapa
// indicePorId (id -> índice da linha). Usado no merge para garantir que um Id
// nunca é escrito por cima de outro jogador — se o Id "preferido" (o que veio
// no .json) já pertence a OUTRA linha, gera-se um novo até ser mesmo único.
function gerarIdUnicoContra(nome, idPreferido, indicePorId) {
    if (idPreferido && indicePorId[idPreferido] === undefined) return idPreferido;
    let candidato;
    do { candidato = gerarIdJogador(nome); } while (indicePorId[candidato] !== undefined);
    return candidato;
}

// O players.csv (export do Genie Scout/FM) traz o nome como "Apelido, Nome"
// (ex: "á Bø, Hans Pauli"). Isto inverte para "Nome Apelido".
function inverterNome(nomeCru) {
    if (!nomeCru || !nomeCru.includes(",")) return nomeCru;
    const partes = nomeCru.split(",").map(s => s.trim());
    const sobrenome = partes[0], nome = partes[1];
    return (nome && sobrenome) ? `${nome} ${sobrenome}` : nomeCru;
}

// Inverso de inverterNome: "Nome Apelido" -> "Apelido, Nome" (formato do CSV).
// Assume que a última palavra é o apelido, o resto é o(s) nome(s) próprio(s).
function reverterNome(nomeCompleto) {
    if (!nomeCompleto) return nomeCompleto;
    const partes = nomeCompleto.trim().split(/\s+/);
    if (partes.length < 2) return nomeCompleto;
    const sobrenome = partes[partes.length - 1];
    const nome = partes.slice(0, -1).join(" ");
    return `${sobrenome}, ${nome}`;
}

// leagues.js (window.LEAGUES_DATA) é estático e mantido à mão (não é gerado pela
// ferramenta) — mapeia País -> Liga -> lista de clubes esperados. Serve só de
// referência para saber a que liga/país pertence cada clube; a validação de quais
// equipas existem de facto vem da contagem de jogadores com atributos+OVER
// carregados com aquele clube no players.csv (20+ jogadores = equipa válida).
// É carregado por <script> (não por fetch) para funcionar também em file://.
const LIGAS_DATA = window.LEAGUES_DATA || {};
const MIN_JOGADORES_PARA_EQUIPA = 20;

// Um jogador só conta para a validação da equipa se tiver TODOS os atributos
// preenchidos + OVER calculável. calcularOverallDinamico já devolve null quando
// falta algum atributo, por isso serve exactamente de teste de "atributos + OVER".
function jogadorTemAtributosCompletos(j) {
    return calcularOverallDinamico(j) !== null;
}

function contarJogadoresPorClube() {
    const contagem = {};
    listaJogadores.forEach(j => {
        const slug = slugifyClube(j.c);
        if (!slug) return;
        if (!jogadorTemAtributosCompletos(j)) return; // só jogadores com atributos + OVER
        contagem[slug] = (contagem[slug] || 0) + 1;
    });
    return contagem;
}

// Bandeira do país: imagem via flagcdn.com (uma "API" de bandeiras por código ISO).
// É só um <img> — se a CDN falhar mostra o emoji de reserva, nunca "buga" o site.
const BANDEIRAS_PAIS = { "Brasil": "🇧🇷", "Portugal": "🇵🇹", "Jamaica": "🇯🇲", "Turquia": "🇹🇷", "Cuba": "🇨🇺", "San Marino": "🇸🇲" };
function bandeiraHtml(pais) {
    const code = ISO_NACOES[(pais || "").toLowerCase()];
    const emoji = BANDEIRAS_PAIS[pais] || "🏳️";
    if (code) {
        return `<img class="pais-bandeira" src="https://flagcdn.com/w40/${code}.png" alt=""
                     loading="lazy" onerror="this.outerHTML='<span class=&quot;pais-bandeira-emoji&quot;>${emoji}</span>'">`;
    }
    return `<span class="pais-bandeira-emoji">${emoji}</span>`;
}

// Formação do "melhor 11": para cada slot escolhem-se os N melhores por OVER
// dentro dos grupos indicados. Assim a média reflecte a MELHOR equipa e não é
// arrastada por reservas/jovens fracos.
//   1 G · 2 L · 2 Z · 4 meio (V/M) · 2 ataque (PE/CA/PD)  = 11
const FORMACAO_XI = [
    { grupos: ["G"], n: 1, linha: "def" },
    { grupos: ["L"], n: 2, linha: "def" },
    { grupos: ["Z"], n: 2, linha: "def" },
    { grupos: ["V", "M"], n: 4, linha: "mei" },
    { grupos: ["PE", "CA", "PD"], n: 2, linha: "ata" },
];

// Agrega por clube: conta jogadores completos e calcula a média do OVER do melhor
// 11 (titulares escolhidos por posição) e por linha (Defesa=G/L/Z, Meio=V/M, Ataque=PE/CA/PD).
function agregarPorClube() {
    const porClube = {};
    listaJogadores.forEach(j => {
        const slug = slugifyClube(j.c);
        if (!slug) return;
        const over = calcularOverallDinamico(j);
        if (over === null) return; // só jogadores completos
        const c = porClube[slug] || (porClube[slug] = { n: 0, grupos: {} });
        c.n++;
        const g = posicaoGrupo(j);
        if (g) (c.grupos[g] = c.grupos[g] || []).push(over);
    });

    const media = arr => (arr.length ? Math.round(arr.reduce((s, x) => s + x, 0) / arr.length) : null);
    const agg = {};
    Object.entries(porClube).forEach(([slug, c]) => {
        const linhas = { def: [], mei: [], ata: [] };
        FORMACAO_XI.forEach(slot => {
            let pool = [];
            slot.grupos.forEach(g => { pool = pool.concat(c.grupos[g] || []); });
            pool.sort((a, b) => b - a);
            linhas[slot.linha] = linhas[slot.linha].concat(pool.slice(0, slot.n));
        });
        const xi = [...linhas.def, ...linhas.mei, ...linhas.ata];
        agg[slug] = { n: c.n, over: media(xi), def: media(linhas.def), mei: media(linhas.mei), ata: media(linhas.ata) };
    });
    return agg;
}

// Mesma escala de cor do OVER, mas para o efeito de pílula (badge).
function classeCorBadge(nota) {
    if (nota === null || nota === undefined || isNaN(nota)) return "sb-nula";
    if (nota >= 80) return "sb-green";
    if (nota >= 70) return "sb-lightgreen";
    if (nota >= 50) return "sb-yellow";
    return "sb-red";
}
function badgeMedia(label, nota) {
    return `<span class="stat-badge ${classeCorBadge(nota)}">${label} ${nota ?? "–"}</span>`;
}

// Estados de abrir/fechar (persistem entre re-renders).
const paisesColapsados = new Set();     // países fechados (por defeito abertos)
const ligasExpandidas = new Set();      // ligas abertas (por defeito fechadas)
function alternarPais(pais, aberto) { if (aberto) paisesColapsados.delete(pais); else paisesColapsados.add(pais); }
function alternarLiga(chave, aberto) { if (aberto) ligasExpandidas.add(chave); else ligasExpandidas.delete(chave); }

// Desenha o painel "Ligas & Países". Cada PAÍS é colapsável (esconde as ligas),
// e cada liga é um accordion compacto que mostra a grelha de clubes com a média
// de OVER/ATA/MEI/DEF do melhor 11.
function atualizarPainelPaises() {
    const conteudo = document.getElementById("paisesConteudo");
    if (!conteudo) return;

    if (!Object.keys(LIGAS_DATA).length) {
        conteudo.innerHTML = `<p class="vazio-msg">leagues.js indisponível (verifica que o ficheiro existe na pasta).</p>`;
        return;
    }

    const agg = agregarPorClube();

    conteudo.innerHTML = Object.entries(LIGAS_DATA).map(([pais, ligas]) => {
        const seccoesLigas = Object.entries(ligas).map(([nomeLiga, clubes]) => {
            const chave = pais + "||" + nomeLiga;
            let validas = 0, somaOver = 0;

            const chips = clubes.map(clube => {
                const a = agg[slugifyClube(clube)];
                const n = a ? a.n : 0;
                const ok = n >= MIN_JOGADORES_PARA_EQUIPA;
                if (ok) {
                    validas++; somaOver += (a.over || 0);
                    return `<div class="clube-chip ok">
                        <div class="chip-top">
                            <span class="clube-chip-nome" title="${clube}">${clube}</span>
                            <span class="clube-chip-count">${n} ✓</span>
                        </div>
                        <div class="chip-medias">
                            ${badgeMedia("OVR", a.over)}
                            ${badgeMedia("ATA", a.ata)}
                            ${badgeMedia("MEI", a.mei)}
                            ${badgeMedia("DEF", a.def)}
                        </div>
                    </div>`;
                }
                return `<div class="clube-chip">
                    <span class="clube-chip-nome" title="${clube}">${clube}</span>
                    <span class="clube-chip-count">${n}/${MIN_JOGADORES_PARA_EQUIPA}</span>
                </div>`;
            }).join("");

            const total = clubes.length;
            const percent = total ? Math.round((validas / total) * 100) : 0;
            const mediaLiga = validas ? Math.round(somaOver / validas) : null;
            const abertoLiga = ligasExpandidas.has(chave) ? " open" : "";

            return `
                <details class="liga-acc"${abertoLiga} ontoggle="alternarLiga('${chave.replace(/'/g, "\\'")}', this.open)">
                    <summary class="liga-summary">
                        <span class="liga-nome">${nomeLiga}</span>
                        <span class="liga-meta">
                            ${mediaLiga != null ? `<span class="liga-media">Média OVR ${mediaLiga}</span>` : ""}
                            <span class="liga-percent-badge">${validas}/${total} válidas · ${percent}%</span>
                            <span class="chevron">▾</span>
                        </span>
                    </summary>
                    <div class="progress-bar" style="margin:10px 14px 0;"><div class="progress-bar-fill" style="width:${percent}%;"></div></div>
                    <div class="clubes-grid">${chips}</div>
                </details>`;
        }).join("");

        const abertoPais = paisesColapsados.has(pais) ? "" : " open";
        return `
            <details class="pais-acc"${abertoPais} ontoggle="alternarPais('${pais.replace(/'/g, "\\'")}', this.open)">
                <summary class="pais-summary">
                    <span class="pais-nome">${bandeiraHtml(pais)} ${pais}</span>
                    <span class="chevron">▾</span>
                </summary>
                <div class="pais-corpo">${seccoesLigas}</div>
            </details>`;
    }).join("");
}

// Troca de aba (puro DOM, sem rede — funciona em file:// e no GitHub Pages).
function trocarAba(nome) {
    document.querySelectorAll(".aba").forEach(s => { s.hidden = (s.id !== "aba-" + nome); });
    document.querySelectorAll(".tab-btn").forEach(b => { b.classList.toggle("active", b.dataset.aba === nome); });
}

let listaJogadores = (window.FM_PLAYERS_DATA || []).map(marcarStatus);
let listaFiltrada = listaJogadores.slice();
let paginaAtual = 1;
const TAMANHO_PAGINA = 50;
let proximoId = 1;

const CHAVE_EDITS = "gofootEdits";
const CHAVE_MANUAIS = "gofootManualPlayers";

let mapaEdicoes = {};
try { mapaEdicoes = JSON.parse(localStorage.getItem(CHAVE_EDITS) || "{}"); } catch (e) { mapaEdicoes = {}; }

const TAG_CATEGORIA = {
    GK: "gk",
    CB: "def", FB: "def", WB: "def",
    DM: "mid", M: "mid", AM: "mid",
    W: "atk", FS: "atk", TS: "atk"
};

function gerarIdentidade(j) {
    return (j.n + "|" + j.nat + "|" + j.c + "|" + j.a).toLowerCase();
}

function marcarStatus(j) {
    j._id = proximoId++;

    const ehGoleiro = posicaoGrupo(j) === "G";
    const atributosOk = ehGoleiro
        ? (j.ref && j.pos_gk && j.aer && j.sai && j.men)
        : (j.tec && j.ata && j.def && j.fis && j.men);

    const valorOk = j.v !== null && j.v !== undefined && j.v !== "-" && j.v !== "" && !isNaN(j.v) && Number(j.v) > 0;

    // VERIFICAÇÃO INTEGRAL DE TODOS OS CAMPOS DO JOGADOR
    j.completo = !!(
        j.n && j.n.trim() !== "" &&
        j.nat && j.nat.trim() !== "" && j.nat !== "-" &&
        j.c && j.c.trim() !== "" && j.c !== "Sem clube" && j.c !== "-" &&
        j.a &&
        j.pe && j.pe !== "-" &&
        j.p && j.p.trim() !== "" &&
        atributosOk &&
        j.tal &&
        valorOk
    );

    j._nLower = (j.n || "").toLowerCase();
    j._natLower = (j.nat || "").toLowerCase();
    j._cLower = (j.c || "").toLowerCase();
    j._pLower = (j.p || "").toLowerCase();
    if (!j.pe) j.pe = "-";
    if (!j.v) j.v = "-";
    return j;
}

document.addEventListener("DOMContentLoaded", () => {
    carregarJogadoresManuais();
    carregarPaises();
    aplicarFiltros();

    // Pré-preenche o mapa de siglas (aba Painel++), se ainda estiver vazio.
    const siglasMapa = document.getElementById("siglasMapa");
    if (siglasMapa && !siglasMapa.value.trim()) siglasMapa.value = MAPA_SIGLAS_PADRAO;

    let debounceTimer = null;
    document.getElementById("searchInput").addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(aplicarFiltros, 250);
    });
});

function carregarJogadoresManuais() {
    try {
        const salvos = JSON.parse(localStorage.getItem(CHAVE_MANUAIS) || "[]");
        salvos.forEach(j => {
            j._manual = true;
            listaJogadores.push(marcarStatus(j));
        });
    } catch (e) { }
}

function salvarJogadoresManuaisNoStorage() {
    const manuais = listaJogadores.filter(j => j._manual);
    localStorage.setItem(CHAVE_MANUAIS, JSON.stringify(manuais));
}

function salvarEdicaoNoStorage(j) {
    mapaEdicoes[gerarIdentidade(j)] = {
        tec: j.tec, ata: j.ata, def: j.def, fis: j.fis, men: j.men,
        ref: j.ref, pos_gk: j.pos_gk, aer: j.aer, sai: j.sai,
        tal: j.tal, pe: j.pe, v: j.v
    };
    localStorage.setItem(CHAVE_EDITS, JSON.stringify(mapaEdicoes));
}

function aplicarEdicoesSalvas(j) {
    const salva = mapaEdicoes[gerarIdentidade(j)];
    if (salva) {
        j.tec = salva.tec; j.ata = salva.ata; j.def = salva.def;
        j.fis = salva.fis; j.men = salva.men; j.tal = salva.tal;
        j.ref = salva.ref; j.pos_gk = salva.pos_gk; j.aer = salva.aer; j.sai = salva.sai;
        j.pe = salva.pe || "-"; j.v = salva.v || "-";
    }
    return j;
}

// Países via API countries.dev — gratuita e sem chave (o restcountries.com
// descontinuou todas as versões anteriores à v5, que agora exige conta+chave).
function carregarPaises() {
    const select = document.getElementById("addNat");
    fetch("https://countries.dev/countries?fields=name,translations&full=true")
        .then(r => { if (!r.ok) throw new Error("Falha na API"); return r.json(); })
        .then(dados => {
            const nomes = dados.map(p => {
                const t = p.translations;
                const pt = (t && typeof t.pt === "string" && t.pt) ||
                           (t && t.pt && t.pt.common) ||
                           (t && t.por && t.por.common);
                return pt || (p.name && p.name.common) || p.name || null;
            }).filter(Boolean);

            if (nomes.length < 50) throw new Error("Resposta da API incompleta");

            // A API só lista estados soberanos, então as nações constituintes do
            // Reino Unido (comuns nos jogos de futebol) não aparecem — adiciona-as à mão.
            nomes.push("Escócia", "País de Gales", "Irlanda do Norte", "Inglaterra");

            nomes.sort((a, b) => a.localeCompare(b, "pt"));
            select.innerHTML = '<option value="">Selecione um país</option>' +
                nomes.map(n => `<option value="${n}">${n}</option>`).join("");
        })
        .catch(() => {
            select.innerHTML = '<option value="">API indisponível — escreva abaixo</option>';
            const input = document.createElement("input");
            input.type = "text"; input.id = "addNatFallback"; input.className = "form-control";
            input.placeholder = "Digite a nação manualmente";
            input.style.marginTop = "8px";
            select.after(input);
        });
}

function obterNacaoSelecionada() {
    const select = document.getElementById("addNat");
    const fallback = document.getElementById("addNatFallback");
    if (fallback && fallback.value.trim()) return fallback.value.trim();
    return select.value || "-";
}

function obterClasseCor(nota) {
    if (!nota) return "score-fifa-red";
    if (nota >= 80) return "score-fifa-green";
    if (nota >= 70) return "score-fifa-lightgreen";
    if (nota >= 50) return "score-fifa-yellow";
    return "score-fifa-red";
}

// Pesos oficiais do OVER por grupo de posição.
// G = Goleiro, Z = Zagueiro, L = Laterais, V = Volante, M = Meiocampista,
// PD/PE = Pontas, CA = Centroavante.
const OVER_WEIGHTS = {
    G:  { REF: 0.20, POS: 0.20, AER: 0.20, SAI: 0.20, MEN: 0.20 },
    Z:  { TEC: 0.15, ATA: 0.05, DEF: 0.40, FIS: 0.25, MEN: 0.15 },
    L:  { TEC: 0.25, ATA: 0.05, DEF: 0.35, FIS: 0.20, MEN: 0.15 },
    V:  { TEC: 0.25, ATA: 0.05, DEF: 0.35, FIS: 0.20, MEN: 0.15 },
    M:  { TEC: 0.35, ATA: 0.30, DEF: 0.05, FIS: 0.10, MEN: 0.20 },
    PD: { TEC: 0.25, ATA: 0.40, DEF: 0.05, FIS: 0.15, MEN: 0.15 },
    PE: { TEC: 0.25, ATA: 0.40, DEF: 0.05, FIS: 0.15, MEN: 0.15 },
    CA: { TEC: 0.20, ATA: 0.40, DEF: 0.05, FIS: 0.20, MEN: 0.15 },
};

// Determina o grupo de posição (G/Z/L/V/M/PD/PE/CA) a partir apenas da
// primeira posição que o jogo/CSV entrega para o jogador.
const GRUPOS_VALIDOS = ["G", "Z", "L", "V", "M", "PD", "PE", "CA"];

function posicaoGrupo(j) {
    const primeira = (j.p || "").split(",")[0].trim().toUpperCase();
    if (!primeira) return null;

    // Já vem como grupo canónico (ex: reimportação de um export nosso) — usa direto.
    if (GRUPOS_VALIDOS.includes(primeira)) return primeira;

    // Códigos curtos (estilo EA FC: gk, cb, lb, rb, lwb, rwb, cdm, cm, lm, rm, cam, lw, rw, cf, st)
    const EA_MAP = {
        GK: "G", CB: "Z",
        LB: "L", RB: "L", LWB: "L", RWB: "L",
        CDM: "V",
        CM: "M", LM: "M", RM: "M", CAM: "M",
        LW: "PE", RW: "PD",
        CF: "CA", ST: "CA",
    };
    if (EA_MAP[primeira]) return EA_MAP[primeira];

    // Notação estilo Football Manager (D C, D L, AM LC, WB R, DM, M C, ST...)
    if (primeira.startsWith("GK") || primeira.startsWith("GR")) return "G";
    if (primeira.startsWith("DM")) return "V";
    if (primeira.startsWith("WB")) return "L";
    if (primeira.startsWith("D")) {
        if (primeira.includes("L") || primeira.includes("R")) return "L";
        return "Z";
    }
    if (primeira.startsWith("AM")) {
        if (primeira.includes("L")) return "PE";
        if (primeira.includes("R")) return "PD";
        return "M";
    }
    if (primeira.startsWith("M")) return "M";
    if (primeira.startsWith("ST") || primeira.startsWith("FW") || primeira.startsWith("CF")) return "CA";

    return null;
}

function calcularOverallDinamico(j) {
    const grupo = posicaoGrupo(j);
    const pesos = OVER_WEIGHTS[grupo];
    if (!pesos) return null;

    const ehGoleiro = grupo === "G";
    const valores = ehGoleiro
        ? { REF: j.ref, POS: j.pos_gk, AER: j.aer, SAI: j.sai, MEN: j.men }
        : { TEC: j.tec, ATA: j.ata, DEF: j.def, FIS: j.fis, MEN: j.men };

    let total = 0;
    for (const chave in pesos) {
        const v = parseFloat(valores[chave]);
        if (isNaN(v)) return null; // só calcula quando todos os atributos existem
        total += v * pesos[chave];
    }
    return Math.round(total);
}

// Valor de mercado (€) gerado a partir do OVER, talento, idade e físico.
// É determinístico: o mesmo jogador dá sempre o mesmo valor (o "ruído" vem de um
// hash, não de aleatório real). Devolve null se faltar OVER/talento/idade.
function calcularValorMercado(j) {
    const overall = calcularOverallDinamico(j);
    const talento = Number(j.tal);
    const idade = Number(j.a);
    if (overall === null || isNaN(talento) || isNaN(idade)) return null;

    let valorBase, fatorIdade;

    if (idade <= 19) {
        const talN = Math.max(0.01, (talento - 30) / 70);
        const ovrN = Math.max(0.01, (overall - 30) / 70);
        valorBase = 20000 + 600000000 * Math.pow(talN, 5.5) * Math.pow(ovrN, 1.5);
        fatorIdade = 1 + (19 - idade) * 0.06;
    } else if (idade <= 33) {
        valorBase = 800000 * Math.exp(0.10 * (overall - 50) + 0.042 * (talento - 50));
        fatorIdade = idade <= 26 ? 1 : 1 - (idade - 26) * 0.08;
    } else {
        // Físico: os guarda-redes não têm FIS, usa-se o Mental como aproximação.
        const ehGoleiro = posicaoGrupo(j) === "G";
        const fisRaw = ehGoleiro ? j.men : j.fis;
        const fisico = (fisRaw !== null && fisRaw !== undefined && !isNaN(fisRaw)) ? Number(fisRaw) : overall;
        valorBase = 5000000 * Math.exp(0.025 * (overall - 50) + 0.010 * (fisico - 50));
        fatorIdade = 0.40 * Math.pow(0.72, idade - 34);
    }

    // Variação determinística de ±5% a partir de um hash.
    const hash = overall * 7919 + idade * 6271 + talento * 3571;
    const noise = 0.95 + ((Math.abs(hash) % 1000) / 1000) * 0.10; // 0.95 .. 1.05
    let valorFinal = valorBase * fatorIdade * noise;

    if (valorFinal < 5000) valorFinal = 5000; // nunca menos que 5.000 €
    return Math.round(valorFinal);
}

// TEMPORÁRIO/dev: recalcula o valor de mercado de TODOS os jogadores carregados
// pela fórmula (só os que têm OVER+talento+idade). Actualiza a tabela e, se vieram
// de CSV, também a coluna Valor da linha original (para o export/regen).
function recalcularValoresMercado() {
    const comRaw = listaJogadores.filter(j => j._csvRaw);
    if (!comRaw.length) {
        alert("Importa primeiro a base com o botão \"Importar Jogadores(.csv)\".");
        return;
    }
    if (!confirm(`Recalcular o valor de mercado dos ${comRaw.length.toLocaleString("pt-PT")} jogadores importados do CSV pela fórmula e descarregar o .csv novo. Continuar?`)) return;

    let feitos = 0, semDados = 0;
    comRaw.forEach(j => {
        const v = calcularValorMercado(j);
        if (v === null) { semDados++; return; }
        j.v = v;
        j._csvRaw.Valor = v;
        marcarStatus(j);
        feitos++;
    });

    // Preserva todas as colunas do CSV original.
    const colunasFinais = [...(colunasCsvImportadas || Object.keys(comRaw[0]._csvRaw))];
    const csvFinal = Papa.unparse(comRaw.map(j => j._csvRaw), { delimiter: ";", columns: colunasFinais });

    // Grava em ISO-8859-1, igual ao que o importarCsv() espera.
    const bytesISO = new Uint8Array(csvFinal.length);
    for (let i = 0; i < csvFinal.length; i++) bytesISO[i] = csvFinal.charCodeAt(i) & 0xFF;
    const blob = new Blob([bytesISO], { type: "text/csv;charset=ISO-8859-1" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "players_valores_recalculados.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    aplicarFiltros();
    alert(`Valores de mercado recalculados: ${feitos.toLocaleString("pt-PT")} jogador(es).` +
        (semDados ? ` ${semDados.toLocaleString("pt-PT")} ficaram de fora (falta OVER/talento/idade).` : "") +
        ` Descarregado "players_valores_recalculados.csv".`);
}

// Calcula, por clube (slug), quantos jogadores tem e quantos são completos
// (atributos+OVER definido). Usado pelos dois selects do Painel++ abaixo.
function estatisticasPorClube() {
    const porSlug = {}; // slug -> { nome, total, completos }
    listaJogadores.forEach(j => {
        const slug = slugifyClube(j.c);
        if (!slug) return;
        const o = porSlug[slug] || (porSlug[slug] = { nome: j.c, total: 0, completos: 0 });
        o.total++;
        if (calcularOverallDinamico(j) !== null) o.completos++;
    });
    return porSlug;
}

// Preenche um <select> só com os clubes que já têm 20+ jogadores completos
// (atributos+OVER definido) — a mesma regra usada na aba Ligas. Clubes ainda
// incompletos não aparecem, para não se mexer por engano num plantel que
// ainda está a ser preenchido. `formatarOpcao(o)` decide o texto de cada opção.
function popularSelectClubesCompletos(idSelect, formatarOpcao, msgVazio) {
    const select = document.getElementById(idSelect);
    if (!select) return;

    const porSlug = estatisticasPorClube();
    const valorSelecionado = select.value;
    const entradas = Object.entries(porSlug)
        .filter(([, o]) => o.completos >= MIN_JOGADORES_PARA_EQUIPA)
        .sort((a, b) => a[1].nome.localeCompare(b[1].nome, "pt"));

    if (!entradas.length) {
        select.innerHTML = `<option value="">${msgVazio}</option>`;
        return;
    }

    select.innerHTML = entradas.map(([slug, o]) => `<option value="${slug}">${formatarOpcao(o)}</option>`).join("");
    if (valorSelecionado && porSlug[valorSelecionado]) select.value = valorSelecionado;
}

function popularSelectApagarClube() {
    popularSelectClubesCompletos(
        "apagarClubeSelect",
        o => `${o.nome} — ${o.completos}/${o.total} completos ✓`,
        "— nenhum clube com 20+ jogadores completos —"
    );
    popularSelectClubesCompletos(
        "limparIncompletosSelect",
        o => `${o.nome} — ${o.completos} completos, ${o.total - o.completos} sem OVER a apagar`,
        "— nenhum clube com 20+ jogadores completos —"
    );
}

// Descarrega o .csv com os jogadores (vindos do CSV, com _csvRaw) actualmente
// em listaJogadores — usado depois de qualquer apagar/limpar no Painel++, para
// a alteração sair logo em ficheiro e não ficar só na sessão do browser.
function descarregarCsvDeListaJogadores(nomeArquivo) {
    const comRaw = listaJogadores.filter(j => j._csvRaw);
    if (!comRaw.length) return; // nada vindo de CSV para escrever (ex: só havia manuais)

    const colunasFinais = [...(colunasCsvImportadas || Object.keys(comRaw[0]._csvRaw))];
    const csvFinal = Papa.unparse(comRaw.map(j => j._csvRaw), { delimiter: ";", columns: colunasFinais });

    const bytesISO = new Uint8Array(csvFinal.length);
    for (let i = 0; i < csvFinal.length; i++) bytesISO[i] = csvFinal.charCodeAt(i) & 0xFF;
    const blob = new Blob([bytesISO], { type: "text/csv;charset=ISO-8859-1" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = nomeArquivo;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// TEMPORÁRIO (dev): apaga da lista carregada TODOS os jogadores do clube
// escolhido (por team_id/slug) — útil para limpar um plantel antigo antes de
// um novo merge. Não mexe no players.csv em disco, só na sessão actual.
function apagarJogadoresDoClube() {
    const select = document.getElementById("apagarClubeSelect");
    const slugAlvo = select ? select.value : "";
    if (!slugAlvo) {
        alert("Escolhe um clube na lista primeiro.");
        return;
    }

    const alvo = listaJogadores.filter(j => slugifyClube(j.c) === slugAlvo);
    if (!alvo.length) {
        alert("Esse clube já não tem jogadores carregados.");
        popularSelectApagarClube();
        return;
    }
    const nomeClube = alvo[0].c;

    if (!confirm(`Isto apaga ${alvo.length.toLocaleString("pt-PT")} jogador(es) do clube "${nomeClube}" da lista carregada (na sessão actual). Não pode ser desfeito. Continuar?`)) return;

    listaJogadores = listaJogadores.filter(j => slugifyClube(j.c) !== slugAlvo);
    salvarJogadoresManuaisNoStorage();
    aplicarFiltros();
    popularSelectApagarClube();
    descarregarCsvDeListaJogadores("players_atualizado.csv");
    alert(`Pronto: ${alvo.length.toLocaleString("pt-PT")} jogador(es) do clube "${nomeClube}" foram apagados. Descarregado "players_atualizado.csv".`);
}

// TEMPORÁRIO (dev): apaga TODOS os jogadores de TODOS os clubes que já têm
// 20+ completos, numa só vez (em vez de ires clube a clube).
function apagarJogadoresDeTodosOsClubesCompletos() {
    const porSlug = estatisticasPorClube();
    const clubesAlvo = Object.entries(porSlug).filter(([, o]) => o.completos >= MIN_JOGADORES_PARA_EQUIPA);

    if (!clubesAlvo.length) {
        alert("Não há nenhum clube com 20+ jogadores completos ainda.");
        return;
    }

    const slugsAlvo = new Set(clubesAlvo.map(([slug]) => slug));
    const total = listaJogadores.filter(j => slugsAlvo.has(slugifyClube(j.c))).length;

    if (!confirm(`Isto apaga TODOS os jogadores (completos e incompletos) de ${clubesAlvo.length.toLocaleString("pt-PT")} clube(s) já completos — ${total.toLocaleString("pt-PT")} jogador(es) no total. Não pode ser desfeito. Continuar?`)) return;

    listaJogadores = listaJogadores.filter(j => !slugsAlvo.has(slugifyClube(j.c)));
    salvarJogadoresManuaisNoStorage();
    aplicarFiltros();
    popularSelectApagarClube();
    alert(`Pronto: ${total.toLocaleString("pt-PT")} jogador(es) apagados de ${clubesAlvo.length.toLocaleString("pt-PT")} clube(s) completos.`);
}

// TEMPORÁRIO (dev): num clube já completo (20+ com OVER), apaga só os
// jogadores SEM OVER (lixo/duplicados incompletos), mantendo os completos.
// Serve para optimizar/limpar a base sem perder o plantel já pronto do clube.
function limparIncompletosDoClube() {
    const select = document.getElementById("limparIncompletosSelect");
    const slugAlvo = select ? select.value : "";
    if (!slugAlvo) {
        alert("Escolhe um clube na lista primeiro.");
        return;
    }

    const doClube = listaJogadores.filter(j => slugifyClube(j.c) === slugAlvo);
    const incompletos = doClube.filter(j => calcularOverallDinamico(j) === null);
    if (!incompletos.length) {
        alert("Esse clube já não tem jogadores sem OVER para apagar.");
        popularSelectApagarClube();
        return;
    }
    const nomeClube = doClube[0].c;
    const completos = doClube.length - incompletos.length;

    if (!confirm(`Isto apaga ${incompletos.length.toLocaleString("pt-PT")} jogador(es) SEM OVER do clube "${nomeClube}" (mantém os ${completos.toLocaleString("pt-PT")} completos). Não pode ser desfeito. Continuar?`)) return;

    const incompletosSet = new Set(incompletos);
    listaJogadores = listaJogadores.filter(j => !incompletosSet.has(j));
    salvarJogadoresManuaisNoStorage();
    aplicarFiltros();
    popularSelectApagarClube();

    descarregarCsvDeListaJogadores("players_clube_limpo.csv");

    alert(`Pronto: ${incompletos.length.toLocaleString("pt-PT")} jogador(es) sem OVER do clube "${nomeClube}" foram apagados. Ficaram ${completos.toLocaleString("pt-PT")} completos.`);
}

// TEMPORÁRIO (dev): em TODOS os clubes já completos (20+ com OVER) de uma só
// vez, apaga os jogadores SEM OVER (lixo/duplicados incompletos), mantendo os
// completos. Não mexe em clubes que ainda não chegaram aos 20 completos.
function limparIncompletosDeTodosOsClubes() {
    const porSlug = estatisticasPorClube();
    const clubesAlvo = Object.entries(porSlug).filter(([, o]) => o.completos >= MIN_JOGADORES_PARA_EQUIPA);

    if (!clubesAlvo.length) {
        alert("Não há nenhum clube com 20+ jogadores completos ainda.");
        return;
    }

    const slugsAlvo = new Set(clubesAlvo.map(([slug]) => slug));
    const incompletos = listaJogadores.filter(j => slugsAlvo.has(slugifyClube(j.c)) && calcularOverallDinamico(j) === null);

    if (!incompletos.length) {
        alert(`Os ${clubesAlvo.length.toLocaleString("pt-PT")} clube(s) completos já não têm jogadores sem OVER para apagar.`);
        return;
    }

    if (!confirm(`Isto apaga ${incompletos.length.toLocaleString("pt-PT")} jogador(es) SEM OVER, espalhados por ${clubesAlvo.length.toLocaleString("pt-PT")} clube(s) já completos (mantém os jogadores completos de cada um). Não pode ser desfeito. Continuar?`)) return;

    const incompletosSet = new Set(incompletos);
    listaJogadores = listaJogadores.filter(j => !incompletosSet.has(j));
    salvarJogadoresManuaisNoStorage();
    aplicarFiltros();
    popularSelectApagarClube();

    descarregarCsvDeListaJogadores("players_clube_limpo.csv");
    
    alert(`Pronto: ${incompletos.length.toLocaleString("pt-PT")} jogador(es) sem OVER apagados em ${clubesAlvo.length.toLocaleString("pt-PT")} clube(s) completos.`);
}

function alternarFiltroStatus(idClicado) {
    const outro = idClicado === "soCompletos" ? "soIncompletos" : "soCompletos";
    if (document.getElementById(idClicado).checked) {
        document.getElementById(outro).checked = false;
    }
    aplicarFiltros();
}

function aplicarFiltros() {
    const termo = document.getElementById("searchInput").value.toLowerCase().trim();
    const soIncompletos = document.getElementById("soIncompletos").checked;
    const soCompletos = document.getElementById("soCompletos").checked;

    if (!termo && !soIncompletos && !soCompletos) {
        listaFiltrada = listaJogadores;
    } else {
        listaFiltrada = listaJogadores.filter(j => {
            if (soIncompletos && j.completo) return false;
            if (soCompletos && !j.completo) return false;
            if (!termo) return true;
            return j._nLower.includes(termo) || j._natLower.includes(termo) ||
                   j._cLower.includes(termo) || j._pLower.includes(termo);
        });
    }
    paginaAtual = 1;
    renderizarPagina();
    atualizarEstatisticas();
    atualizarPainelPaises();
    popularSelectApagarClube();
}

function atualizarEstatisticas() {
    const completos = listaJogadores.filter(j => j.completo).length;
    document.getElementById("statTotal").textContent = `Total: ${listaJogadores.length.toLocaleString("pt-PT")}`;
    document.getElementById("statCompletos").textContent = `Completos: ${completos.toLocaleString("pt-PT")}`;
    document.getElementById("statIncompletos").textContent = `Incompletos: ${(listaJogadores.length - completos).toLocaleString("pt-PT")}`;
}

// Ordenação da tabela: clicar num cabeçalho cicla 1º clique = crescente/A-Z,
// 2º clique = decrescente/Z-A, 3º clique = volta à ordem por defeito (sem ordenar).
let ordenacaoAtual = { coluna: null, direcao: null };

function valorOrdenacao(j, coluna) {
    const ehGoleiro = posicaoGrupo(j) === "G";
    switch (coluna) {
        case "nome": return (j.n || "").toLowerCase();
        case "nacao": return (j.nat || "").toLowerCase();
        case "clube": return (j.c || "").toLowerCase();
        case "idade": return Number(j.a) || 0;
        case "pe": return (j.pe || "").toLowerCase();
        case "posicao": return (posicaoGrupo(j) || j.p || "").toLowerCase();
        case "geral": { const v = calcularOverallDinamico(j); return v === null ? -1 : v; }
        case "attr1": { const v = ehGoleiro ? j.ref : j.tec; return v === null || v === undefined ? -1 : Number(v); }
        case "attr2": { const v = ehGoleiro ? j.pos_gk : j.ata; return v === null || v === undefined ? -1 : Number(v); }
        case "attr3": { const v = ehGoleiro ? j.aer : j.def; return v === null || v === undefined ? -1 : Number(v); }
        case "attr4": { const v = ehGoleiro ? j.sai : j.fis; return v === null || v === undefined ? -1 : Number(v); }
        case "mental": return (j.men === null || j.men === undefined) ? -1 : Number(j.men);
        case "talento": return (j.tal === null || j.tal === undefined) ? -1 : Number(j.tal);
        case "valor": { const v = Number(j.v); return isNaN(v) ? -1 : v; }
        case "status": return j.completo ? 1 : 0;
        default: return 0;
    }
}

function ordenarLista(lista) {
    if (!ordenacaoAtual.coluna || !ordenacaoAtual.direcao) return lista;
    const copia = lista.slice();
    copia.sort((a, b) => {
        const va = valorOrdenacao(a, ordenacaoAtual.coluna);
        const vb = valorOrdenacao(b, ordenacaoAtual.coluna);
        const cmp = (typeof va === "string") ? va.localeCompare(vb, "pt") : va - vb;
        return ordenacaoAtual.direcao === "asc" ? cmp : -cmp;
    });
    return copia;
}

function atualizarIndicadoresOrdenacao() {
    document.querySelectorAll(".th-sort").forEach(th => {
        th.classList.remove("sort-asc", "sort-desc");
        if (th.dataset.coluna === ordenacaoAtual.coluna) {
            th.classList.add(ordenacaoAtual.direcao === "asc" ? "sort-asc" : "sort-desc");
        }
    });
}

function ordenarPor(coluna) {
    if (ordenacaoAtual.coluna !== coluna) {
        ordenacaoAtual = { coluna, direcao: "asc" };
    } else if (ordenacaoAtual.direcao === "asc") {
        ordenacaoAtual.direcao = "desc";
    } else {
        ordenacaoAtual = { coluna: null, direcao: null }; // 3º clique: volta ao default
    }
    atualizarIndicadoresOrdenacao();
    renderizarPagina();
}

function renderizarPagina() {
    const dadosOrdenados = ordenarLista(listaFiltrada);
    const inicio = (paginaAtual - 1) * TAMANHO_PAGINA;
    const pagina = dadosOrdenados.slice(inicio, inicio + TAMANHO_PAGINA);
    renderizarTabela(pagina);
    renderizarPaginacao();
}

function renderizarPaginacao() {
    const totalPaginas = Math.max(1, Math.ceil(listaFiltrada.length / TAMANHO_PAGINA));
    const bar = document.getElementById("paginationBar");
    bar.innerHTML = `
        <button onclick="irParaPagina(1)" ${paginaAtual === 1 ? "disabled" : ""}>«</button>
        <button onclick="irParaPagina(${paginaAtual - 1})" ${paginaAtual === 1 ? "disabled" : ""}>‹ Anterior</button>
        <span>Página ${paginaAtual} de ${totalPaginas} — ${listaFiltrada.length.toLocaleString("pt-PT")} jogadores</span>
        <button onclick="irParaPagina(${paginaAtual + 1})" ${paginaAtual === totalPaginas ? "disabled" : ""}>Próxima ›</button>
        <button onclick="irParaPagina(${totalPaginas})" ${paginaAtual === totalPaginas ? "disabled" : ""}>»</button>
    `;
}

function irParaPagina(n) {
    const totalPaginas = Math.max(1, Math.ceil(listaFiltrada.length / TAMANHO_PAGINA));
    paginaAtual = Math.min(Math.max(1, n), totalPaginas);
    renderizarPagina();
}

// Só para exibição na tabela — o valor real (j.v) fica sempre em número puro.
function formatarValorMercado(v) {
    const n = Number(v);
    if (v === null || v === undefined || v === "-" || v === "" || isNaN(n)) return "-";
    if (n >= 1000000) return (n / 1000000).toFixed(n % 1000000 === 0 ? 0 : 1).replace(/\.0$/, "") + "M€";
    if (n >= 1000) return (n / 1000).toFixed(n % 1000 === 0 ? 0 : 1).replace(/\.0$/, "") + "K€";
    return n + "€";
}

function linhaTabela(j) {
    j.ov = calcularOverallDinamico(j);
    const statusClass = j.completo ? "status-completo" : "status-incompleto";
    const statusTxt = j.completo ? "Completo" : "Incompleto";
    const ehGoleiro = posicaoGrupo(j) === "G";
    const col1 = ehGoleiro ? j.ref : j.tec;
    const col2 = ehGoleiro ? j.pos_gk : j.ata;
    const col3 = ehGoleiro ? j.aer : j.def;
    const col4 = ehGoleiro ? j.sai : j.fis;
    return `
        <tr>
            <td style="font-weight: 600;">${j.n || "-"}</td>
            <td style="color: #8b949e;">${j.nat && j.nat !== "-" ? j.nat.toUpperCase() : "-"}</td>
            <td>${j.c || "-"}</td>
            <td>${j.a || "-"}</td>
            <td style="color: #8b949e; font-size: 13px;">${j.pe || "-"}</td>
            <td style="text-transform: uppercase; font-size: 13px; color: #8b949e;">${posicaoGrupo(j) || j.p || "-"}</td>
            <td class="badge-score ${obterClasseCor(j.ov)}">${j.ov || "-"}</td>
            <td class="badge-score ${obterClasseCor(col1)}">${col1 || "-"}</td>
            <td class="badge-score ${obterClasseCor(col2)}">${col2 || "-"}</td>
            <td class="badge-score ${obterClasseCor(col3)}">${col3 || "-"}</td>
            <td class="badge-score ${obterClasseCor(col4)}">${col4 || "-"}</td>
            <td class="badge-score ${obterClasseCor(j.men)}">${j.men || "-"}</td>
            <td class="badge-score ${obterClasseCor(j.tal)}">${j.tal || "-"}</td>
            <td style="font-weight: 500; color: #58a6ff;">${formatarValorMercado(j.v)}</td>
            <td><span class="status-badge ${statusClass}">${statusTxt}</span></td>
            <td>
                <button class="btn-edit" onclick="abrirModal(${j._id})" title="Editar">✎</button>
                <button class="btn-delete" onclick="excluirJogador(${j._id})" title="Excluir">✕</button>
            </td>
        </tr>`;
}

function renderizarTabela(dados) {
    const tbodyLinha = document.getElementById("playerTableBody");
    const tbodyGk = document.getElementById("gkTableBody");
    const wrapLinha = document.getElementById("wrapLinha");
    const wrapGoleiro = document.getElementById("wrapGoleiro");

    const linha = dados.filter(j => posicaoGrupo(j) !== "G");
    const goleiros = dados.filter(j => posicaoGrupo(j) === "G");

    wrapLinha.style.display = linha.length ? "block" : "none";
    wrapGoleiro.style.display = goleiros.length ? "block" : "none";

    if (dados.length === 0) {
        wrapLinha.style.display = "block";
        tbodyLinha.innerHTML = `<tr><td colspan="16" style="text-align:center; color:#8b949e; padding: 24px;">Nenhum jogador encontrado.</td></tr>`;
        return;
    }

    tbodyLinha.innerHTML = linha.map(linhaTabela).join("");
    tbodyGk.innerHTML = goleiros.map(linhaTabela).join("");
}

function abrirModal(id) {
    const modal = document.getElementById("playerModal");
    const titulo = document.getElementById("modalTitulo");
    const btnSalvar = document.getElementById("btnSalvarModal");
    document.getElementById("editandoId").value = "";

    if (id) {
        const j = listaJogadores.find(p => p._id === id);
        if (!j) return;
        document.getElementById("editandoId").value = id;
        titulo.textContent = "Editar Jogador";
        btnSalvar.textContent = "Guardar Alterações";
        document.getElementById("addNome").value = j.n || "";
        document.getElementById("addClube").value = j.c && j.c !== "-" ? j.c : "";
        document.getElementById("addIdade").value = j.a || "";
        document.getElementById("addPe").value = j.pe && j.pe !== "-" ? j.pe : "Direito";
        document.getElementById("addPos").value = j.p || "";
        document.getElementById("addTec").value = j.tec || "";
        document.getElementById("addAta").value = j.ata || "";
        document.getElementById("addDef").value = j.def || "";
        document.getElementById("addFis").value = j.fis || "";
        document.getElementById("addMen").value = j.men || "";
        document.getElementById("addRef").value = j.ref || "";
        document.getElementById("addPosGk").value = j.pos_gk || "";
        document.getElementById("addAer").value = j.aer || "";
        document.getElementById("addSai").value = j.sai || "";
        document.getElementById("addTalento").value = j.tal || "";
        document.getElementById("addValor").value = j.v && j.v !== "-" ? j.v : "";

        const select = document.getElementById("addNat");
        const fallback = document.getElementById("addNatFallback");
        if ([...select.options].some(o => o.value === j.nat)) {
            select.value = j.nat;
        } else if (fallback) {
            fallback.value = j.nat && j.nat !== "-" ? j.nat : "";
        }
        atualizarCamposPorPosicao();
    } else {
        titulo.textContent = "Adicionar Novo Jogador";
        btnSalvar.textContent = "Salvar Jogador";
        document.getElementById("playerForm").reset();
        atualizarCamposPorPosicao();
    }

    modal.style.display = "flex";
}

function atualizarCamposPorPosicao() {
    const grupo = posicaoGrupo({ p: document.getElementById("addPos").value });
    const ehGoleiro = grupo === "G";
    document.getElementById("camposLinha").style.display = ehGoleiro ? "none" : "block";
    document.getElementById("camposGoleiro").style.display = ehGoleiro ? "block" : "none";
}

function fecharModal() {
    document.getElementById("playerModal").style.display = "none";
    document.getElementById("playerForm").reset();
}

function salvarJogador(e) {
    e.preventDefault();
    const idEditando = parseInt(document.getElementById("editandoId").value) || null;

    const dadosForm = {
        n: document.getElementById("addNome").value,
        nat: obterNacaoSelecionada(),
        c: document.getElementById("addClube").value.trim() || "-",
        a: parseInt(document.getElementById("addIdade").value),
        pe: document.getElementById("addPe").value,
        p: document.getElementById("addPos").value.toLowerCase().replace(/\s/g, ""),
        men: parseInt(document.getElementById("addMen").value),
        tal: parseInt(document.getElementById("addTalento").value) || null
    };

    const ehGoleiro = posicaoGrupo(dadosForm) === "G";
    if (ehGoleiro) {
        dadosForm.ref = parseInt(document.getElementById("addRef").value) || null;
        dadosForm.pos_gk = parseInt(document.getElementById("addPosGk").value) || null;
        dadosForm.aer = parseInt(document.getElementById("addAer").value) || null;
        dadosForm.sai = parseInt(document.getElementById("addSai").value) || null;
        dadosForm.tec = null; dadosForm.ata = null; dadosForm.def = null; dadosForm.fis = null;
    } else {
        dadosForm.tec = parseInt(document.getElementById("addTec").value) || null;
        dadosForm.ata = parseInt(document.getElementById("addAta").value) || null;
        dadosForm.def = parseInt(document.getElementById("addDef").value) || null;
        dadosForm.fis = parseInt(document.getElementById("addFis").value) || null;
        dadosForm.ref = null; dadosForm.pos_gk = null; dadosForm.aer = null; dadosForm.sai = null;
    }

    // O valor de mercado é GERADO pela fórmula depois de todos os atributos
    // estarem definidos (o campo no formulário está bloqueado). Se ainda não
    // houver OVER/talento/idade suficientes, fica "-".
    dadosForm.v = calcularValorMercado(dadosForm) ?? "-";

    if (idEditando) {
        const j = listaJogadores.find(p => p._id === idEditando);
        Object.assign(j, dadosForm);
        marcarStatus(j);
        j._id = idEditando;

        if (j._manual) {
            salvarJogadoresManuaisNoStorage();
        } else {
            salvarEdicaoNoStorage(j);
        }
    } else {
        dadosForm.id = gerarIdJogador(dadosForm.n);
        const novo = marcarStatus({ ...dadosForm, _manual: true });
        listaJogadores.unshift(novo);
        salvarJogadoresManuaisNoStorage();
    }

    aplicarFiltros();
    fecharModal();
}

function excluirJogador(id) {
    const idx = listaJogadores.findIndex(p => p._id === id);
    if (idx === -1) return;
    const era_manual = listaJogadores[idx]._manual;
    listaJogadores.splice(idx, 1);
    if (era_manual) salvarJogadoresManuaisNoStorage();
    aplicarFiltros();
}

function limparTabela() {
    if (confirm("Tem certeza que deseja apagar todos os jogadores exibidos?")) {
        listaJogadores = [];
        salvarJogadoresManuaisNoStorage();
        aplicarFiltros();
    }
}

function importarCsv(event) {
    const arquivo = event.target.files[0];
    if (!arquivo) return;

    const overlay = document.getElementById("loadingOverlay");
    const texto = document.getElementById("loadingText");
    overlay.style.display = "flex";
    texto.textContent = "A importar base de dados...";

    Papa.parse(arquivo, {
        header: true,
        delimiter: ";",
        skipEmptyLines: true,
        encoding: "ISO-8859-1",
        worker: true,
        complete: function (resultado) {
            const linhas = resultado.data;
            const novosJogadores = [];
            // Guarda as colunas do CSV para poder reescrevê-lo (ex: regenerar IDs).
            colunasCsvImportadas = resultado.meta.fields;

            for (const linha of linhas) {
                if (!linha.Name) continue;

                const tagMatch = (linha["Best Rating"] || "").match(/\(([A-Za-z]+)\)/);
                const tag = tagMatch ? tagMatch[1] : null;

                const nomeCerto = inverterNome(linha.Name);
                const numOuNull = v => (v !== undefined && v !== null && v !== "" && !isNaN(v)) ? Number(v) : null;
                const jogador = {
                    id: linha.Id || gerarIdJogador(nomeCerto),
                    n: nomeCerto,
                    nat: linha.Nation || "-",
                    c: linha.Club && linha.Club !== "-" ? linha.Club : "-",
                    a: parseInt(linha.Age) || null,
                    // Posicao (grupo canónico, ex: "Z") tem prioridade sobre Position (notação FM, ex: "D C")
                    p: linha.Posicao || linha.Position || "",
                    catg: TAG_CATEGORIA[tag] || null,
                    pe: PE_LETRA_INVERSO[linha.Pe] || "-",
                    v: numOuNull(linha.Valor) ?? "-",
                    tec: numOuNull(linha.TEC), ata: numOuNull(linha.ATA), def: numOuNull(linha.DEF), fis: numOuNull(linha.FIS), men: numOuNull(linha.MEN),
                    ref: numOuNull(linha.REF), pos_gk: numOuNull(linha.POS_GK), aer: numOuNull(linha.AER), sai: numOuNull(linha.SAI),
                    tal: numOuNull(linha.TAL)
                };

                // Mantém a linha original do CSV para poder reescrever o ficheiro
                // completo (todas as colunas) na regeneração de IDs.
                jogador._csvRaw = linha;

                aplicarEdicoesSalvas(jogador);
                novosJogadores.push(marcarStatus(jogador));
            }

            listaJogadores = listaJogadores.filter(j => j._manual).concat(novosJogadores);
            aplicarFiltros();

            overlay.style.display = "none";
            alert(`Importação concluída: ${novosJogadores.length.toLocaleString("pt-PT")} jogadores carregados.`);
        },
        error: function (erro) {
            overlay.style.display = "none";
            alert("Erro ao processar o .csv: " + erro.message);
        }
    });

    event.target.value = "";
}

const PE_LETRA = { "Direito": "D", "Esquerdo": "E", "Ambidestro": "A" };
const PE_LETRA_INVERSO = { "D": "Direito", "E": "Esquerdo", "A": "Ambidestro" };

// Correcções de team_id: alguns exports trazem o mesmo clube com um team_id
// diferente (erro de grafia na fonte, ex: "Ciego de Aliva" vs "Ciego de Ávila").
// Aplicado logo na entrada dos dados para que ambos contem como o MESMO clube
// em vez de ficarem divididos em duas entradas com metade dos jogadores cada.
const CORRECAO_TEAM_ID = {
    "ciego_de_aliva_fc": "ciego_de_avila_fc",
};
function corrigirTeamId(teamId) {
    return CORRECAO_TEAM_ID[teamId] || teamId;
}

// Nome do clube -> slug (minúsculas, sem acentos/espaços) para usar como team_id.
function slugifyClube(nomeClube) {
    if (!nomeClube || nomeClube === "-") return null;
    return nomeClube
        .normalize("NFD").replace(/[̀-ͯ]/g, "")
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
}

// Slug -> nome legível (aproximado; não recupera capitalização exacta de
// clubes com nomes irregulares tipo "AC Milan", mas serve para o essencial).
function deslugifyClube(slug) {
    if (!slug) return "-";
    return slug.split("_").map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

// Converte um jogador vindo de um export no formato do GoFoot (nome, idade,
// TEC/ATA/..., posicao como letra) de volta para o formato interno do painel
// (n, a, tec/ata/..., p). Se já vier no formato interno, devolve como está.
function converterImportGoFoot(j) {
    if (j.n !== undefined && j.p !== undefined) return j; // já é formato interno

    const interno = {
        id: j.id || gerarIdJogador(j.nome),
        n: j.nome || "",
        nat: j.nacionalidade || "-",
        c: deslugifyClube(corrigirTeamId(j.team_id)),
        a: j.idade || null,
        pe: PE_LETRA_INVERSO[j.pe] || "-",
        p: j.posicao || "",
        v: (j.valor !== null && j.valor !== undefined) ? j.valor : "-",
        tal: j.TAL ?? null,
    };

    // Usa posicaoGrupo (não j.posicao === "G") porque a posição pode vir como
    // código bruto do FM/EA (ex: "GK") em vez do grupo canónico "G" — senão os
    // atributos de guarda-redes (REF/POS/AER/SAI) eram descartados e o OVER ficava null.
    if (posicaoGrupo({ p: j.posicao }) === "G") {
        interno.ref = j.REF ?? null;
        interno.pos_gk = j.POS ?? null;
        interno.aer = j.AER ?? null;
        interno.sai = j.SAI ?? null;
        interno.men = j.MEN ?? null;
        interno.tec = null; interno.ata = null; interno.def = null; interno.fis = null;
    } else {
        interno.tec = j.TEC ?? null;
        interno.ata = j.ATA ?? null;
        interno.def = j.DEF ?? null;
        interno.fis = j.FIS ?? null;
        interno.men = j.MEN ?? null;
        interno.ref = null; interno.pos_gk = null; interno.aer = null; interno.sai = null;
    }

    return interno;
}

// Monta o objeto exatamente no formato de import do jogo GoFoot.
// Só os campos que o painel realmente controla saem preenchidos; tudo o resto
// (contrato, avatar, estatísticas de carreira, etc.) sai null, porque essa
// informação não existe aqui — fica a cargo do próprio jogo.
function montarExportGoFoot(j) {
    const ehGoleiro = posicaoGrupo(j) === "G";

    const saida = {
        id: j.id || gerarIdJogador(j.n),
        nome: j.n || null,
        idade: j.a || null,
        nacionalidade: resolverNacaoISO(j.nat),
        numero: null,
        pe: PE_LETRA[j.pe] || null,
        posicao: posicaoGrupo(j),
        TAL: j.tal ?? null,
        salario: null,
        valor: (j.v !== null && j.v !== undefined && j.v !== "-" && !isNaN(j.v)) ? Number(j.v) : null,
        team_id: slugifyClube(j.c),
        energia: 100,
        lesionado: null,
        diasLesao: null,
        suspenso: false,
        fimContrato: null,
        cartoes_amarelos: null,
        cartoes_vermelhos: null,
        golsCarreira: null,
        golsTemporada: null,
        assistenciasCarreira: null,
        assistenciasTemporada: null,
        jogosCarreira: null,
        jogosTemporada: null,
        caracteristicas: null,
        avatar_body: null, avatar_body_color: null, avatar_body_white_mix: null,
        avatar_hair: null, avatar_hair_color: null, avatar_hair_white_mix: null,
        avatar_beard: null, avatar_beard_color: null, avatar_beard_white_mix: null,
        avatar_shirt: null,
        avatar_color: null,
        avatar_earring: null, avatar_earring_color: null, avatar_earring_white_mix: null,
        avatar_tattoo: null, avatar_tattoo_color: null, avatar_tattoo_white_mix: null,
    };

    if (ehGoleiro) {
        saida.REF = j.ref ?? null;
        saida.POS = j.pos_gk ?? null;
        saida.AER = j.aer ?? null;
        saida.SAI = j.sai ?? null;
        saida.MEN = j.men ?? null;
    } else {
        saida.TEC = j.tec ?? null;
        saida.ATA = j.ata ?? null;
        saida.DEF = j.def ?? null;
        saida.FIS = j.fis ?? null;
        saida.MEN = j.men ?? null;
    }
    saida.OVER = calcularOverallDinamico(j);

    return saida;
}

function baixarJSON(lista, nomeArquivo) {
    // Sem indentação: para listas grandes (dezenas/centenas de milhares de
    // jogadores) a indentação sozinha pode multiplicar o tamanho do ficheiro
    // por 3-4x, o que dificulta reimportar depois.
    const conteudoJSON = JSON.stringify(lista);
    const blob = new Blob([conteudoJSON], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = nomeArquivo;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function exportarDados() {
    if (listaJogadores.length === 0) {
        alert("Não há jogadores para exportar.");
        return;
    }
    baixarJSON(listaJogadores.map(montarExportGoFoot), "fm_players.json");
}

// Colunas do último players.csv importado (para reescrever o ficheiro completo).
let colunasCsvImportadas = null;

// TEMPORÁRIO: gera um ID único novo para os jogadores JÁ IMPORTADOS do players.csv
// e descarrega o .csv (db completa, todas as colunas preservadas). Serve para
// migrar uma base com IDs repetidos/antigos. Remover botão/função depois.
function regenerarIdsCsv() {
    const comRaw = listaJogadores.filter(j => j._csvRaw);
    if (!comRaw.length) {
        alert("Importa primeiro a base com o botão \"Importar Jogadores(.csv)\".");
        return;
    }
    if (!confirm(`Isto gera um ID único novo para os ${comRaw.length.toLocaleString("pt-PT")} jogadores importados do CSV e descarrega o .csv novo. Continuar?`)) return;

    comRaw.forEach(j => {
        const novoId = gerarIdJogador(j.n);
        j.id = novoId;
        j._csvRaw.Id = novoId;
    });

    // Preserva todas as colunas do CSV original; só garante que "Id" existe.
    const colunasFinais = [...(colunasCsvImportadas || Object.keys(comRaw[0]._csvRaw))];
    if (!colunasFinais.includes("Id")) colunasFinais.push("Id");
    const csvFinal = Papa.unparse(comRaw.map(j => j._csvRaw), { delimiter: ";", columns: colunasFinais });

    // Grava em ISO-8859-1, igual ao que o importarCsv() espera.
    const bytesISO = new Uint8Array(csvFinal.length);
    for (let i = 0; i < csvFinal.length; i++) bytesISO[i] = csvFinal.charCodeAt(i) & 0xFF;
    const blob = new Blob([bytesISO], { type: "text/csv;charset=ISO-8859-1" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "players_ids_unicos.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    aplicarFiltros();
    alert(`Pronto: ${comRaw.length.toLocaleString("pt-PT")} linhas com IDs únicos novos. Descarregado "players_ids_unicos.csv" — usa esse como a tua db a partir de agora.`);
}

// Mapa por defeito de siglas -> nome completo (editável na aba Painel++).
// SIGLA=Nome. Linhas em branco ou a começar por # são ignoradas.
const MAPA_SIGLAS_PADRAO = `# Brasil — SIGLA=Nome do clube (baseado no team_id dos .json das equipas)
SPO=São Paulo
BOT=Botafogo
VIT=Vitória
COR=Corinthians
SAN=Santos
SEP=Palmeiras
REM=Remo
CRI=Criciúma
BAH=Bahia
CRT=Coritiba
MIR=Mirassol
CHA=Chapecoense
CEC=Cruzeiro
BRA=RB Bragantino
CAP=Atlético Paranaense
GREMIO=Grêmio
ATM=Atlético Mineiro
FOR=Fortaleza
SPT=Sport Recife
INT=Internacional
FLU=Fluminense
Vasco Da Gama=Vasco
# Portugal
BRG=SC Braga
VTSC=Vitória SC`;

// Converte o texto do mapa (SIGLA=Nome, uma por linha) num objecto { sigla: nome }.
function lerMapaSiglas(texto) {
    const mapa = {};
    (texto || "").split(/\r?\n/).forEach(linha => {
        const l = linha.trim();
        if (!l || l.startsWith("#")) return;
        const i = l.indexOf("=");
        if (i < 1) return;
        const sigla = l.slice(0, i).trim();
        const nome = l.slice(i + 1).trim();
        if (sigla && nome) mapa[sigla] = nome;
    });
    return mapa;
}

// TEMPORÁRIO (dev): troca as siglas dos clubes na coluna Club do players.csv
// importado pelos nomes completos, segundo o mapa da textarea, e descarrega o .csv.
function traduzirSiglas() {
    const status = document.getElementById("statusTraduzirSiglas");
    const comRaw = listaJogadores.filter(j => j._csvRaw);
    if (!comRaw.length) {
        status.textContent = "Importa primeiro a base na aba Jogadores (Importar Jogadores.csv).";
        return;
    }

    const mapa = lerMapaSiglas(document.getElementById("siglasMapa").value);
    if (!Object.keys(mapa).length) {
        status.textContent = "O mapa de siglas está vazio.";
        return;
    }
    if (!confirm("Isto troca as siglas dos clubes pelos nomes completos (segundo o mapa) e descarrega o .csv. Continuar?")) return;

    // Índice de procura insensível a maiúsculas/minúsculas — na base as siglas
    // aparecem em várias caixas ("SPO" vazio vs "Spo" preenchido), por isso a
    // comparação tem de ignorar a caixa para apanhar todas as linhas.
    const mapaUpper = {};
    Object.entries(mapa).forEach(([sigla, nome]) => { mapaUpper[sigla.trim().toUpperCase()] = nome; });

    let trocados = 0;
    comRaw.forEach(j => {
        const clubeAtual = (j._csvRaw.Club || "").trim();
        const nome = mapaUpper[clubeAtual.toUpperCase()];
        if (nome) {
            j._csvRaw.Club = nome;
            j.c = nome;
            trocados++;
        }
    });

    const colunasFinais = [...(colunasCsvImportadas || Object.keys(comRaw[0]._csvRaw))];
    const csvFinal = Papa.unparse(comRaw.map(j => j._csvRaw), { delimiter: ";", columns: colunasFinais });

    const bytesISO = new Uint8Array(csvFinal.length);
    for (let i = 0; i < csvFinal.length; i++) bytesISO[i] = csvFinal.charCodeAt(i) & 0xFF;
    const blob = new Blob([bytesISO], { type: "text/csv;charset=ISO-8859-1" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "players_siglas_traduzidas.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    aplicarFiltros();
    status.textContent = `Pronto: ${trocados.toLocaleString("pt-PT")} linha(s) com clube traduzido. Descarregado "players_siglas_traduzidas.csv".`;
}

function exportarDadosFiltrados() {
    if (listaFiltrada.length === 0) {
        alert("Não há jogadores exibidos no filtro atual para exportar.");
        return;
    }
    const termoBusca = document.getElementById("searchInput").value.trim().toLowerCase().replace(/[^a-z0-9]/g, '_');
    const nomeArquivo = termoBusca ? `fm_players_filtrado_${termoBusca}.json` : "fm_players_filtrado.json";
    baixarJSON(listaFiltrada.map(montarExportGoFoot), nomeArquivo);
}

function importarDados(event) {
    const arquivos = Array.from(event.target.files);
    if (!arquivos.length) return;

    const overlay = document.getElementById("loadingOverlay");
    const texto = document.getElementById("loadingText");
    overlay.style.display = "flex";
    texto.textContent = arquivos.length > 1
        ? `Importando ${arquivos.length} ficheiros .json...`
        : "Importando ficheiro .json...";

    // Lê todos os ficheiros seleccionados e junta os jogadores de todos numa só lista.
    Promise.all(arquivos.map(lerJsonComoTexto))
        .then(textos => {
            // setTimeout dá tempo ao overlay de aparecer antes do parse pesado bloquear a aba
            setTimeout(() => {
                try {
                    let bruto = [];
                    textos.forEach((texto, i) => {
                        const lista = JSON.parse(texto);
                        if (!Array.isArray(lista)) throw new Error(`"${arquivos[i].name}" não contém uma lista de jogadores`);
                        bruto = bruto.concat(lista);
                    });

                    // Nota: ao contrário do "Adicionar Jogador" manual, uma importação em massa
                    // não é gravada jogador-a-jogador no localStorage — para milhares de
                    // jogadores isso excederia a quota do browser (uns 5-10MB) e ficaria cada
                    // vez mais lento. Fica só na sessão atual; exporta de novo para guardar.
                    const dadosCarregados = bruto.map(converterImportGoFoot).map(marcarStatus);

                    listaJogadores = listaJogadores.filter(j => j._manual).concat(dadosCarregados);
                    aplicarFiltros();
                    overlay.style.display = "none";
                    alert(`Sucesso! ${dadosCarregados.length.toLocaleString("pt-PT")} jogadores importados de ${arquivos.length} ficheiro(s).`);
                } catch (erro) {
                    overlay.style.display = "none";
                    alert("Não foi possível ler o(s) ficheiro(s) .json: " + erro.message);
                }
            }, 50);
        })
        .catch(erro => {
            overlay.style.display = "none";
            alert("Erro ao ler o(s) ficheiro(s): " + erro.message);
        });

    event.target.value = "";
}

// Nome normalizado para comparação: minúsculas, sem acentos, palavras
// ordenadas — assim "Apelido, Nome" e "Nome Apelido" batem certo na mesma.
function normalizarNomeParaMatch(nome) {
    return (nome || "")
        .normalize("NFD").replace(/[̀-ͯ]/g, "")
        .toLowerCase()
        .split(/[\s,]+/).filter(Boolean).sort().join(" ");
}

const NOVAS_COLUNAS_CSV = ["Id", "Pe", "Posicao", "TAL", "Valor", "TEC", "ATA", "DEF", "FIS", "MEN", "REF", "POS_GK", "AER", "SAI", "OVER"];

// Lê o players.csv mestre + um .json de equipa (no formato de export do
// GoFoot, com ou sem "id"), actualiza só as linhas dos jogadores que aparecem
// na equipa (atribuindo Id se ainda não tiverem), e devolve um novo CSV para
// descarregar — as restantes linhas do CSV ficam exactamente como estavam.
function lerJsonComoTexto(arquivo) {
    return new Promise((resolve, reject) => {
        const leitor = new FileReader();
        leitor.onload = e => resolve(e.target.result);
        leitor.onerror = () => reject(new Error(`falha ao ler "${arquivo.name}"`));
        leitor.readAsText(arquivo);
    });
}

function atualizarCsvComEquipa() {
    const arquivoCsv = document.getElementById("csvMestreInput").files[0];
    const arquivosJson = Array.from(document.getElementById("equipaJsonInput").files);
    const status = document.getElementById("statusAtualizacaoCsv");

    if (!arquivoCsv || !arquivosJson.length) {
        status.textContent = "Escolhe o CSV mestre e pelo menos um .json de equipa.";
        return;
    }

    status.textContent = "A processar...";

    // Cada jogador já traz o seu próprio team_id, por isso vários .json de
    // equipas diferentes podem ser seleccionados de uma vez — junta-se tudo
    // numa única lista antes de fazer o merge com o CSV mestre.
    Promise.all(arquivosJson.map(lerJsonComoTexto))
        .then(textos => {
            let equipa = [];
            textos.forEach((texto, i) => {
                const lista = JSON.parse(texto);
                if (!Array.isArray(lista)) throw new Error(`"${arquivosJson[i].name}" não é uma lista`);
                // Corrige team_ids duplicados/com erro de grafia (ver CORRECAO_TEAM_ID)
                // logo na entrada, para o merge tratar sempre como o mesmo clube.
                lista.forEach(j => { if (j.team_id) j.team_id = corrigirTeamId(j.team_id); });
                equipa = equipa.concat(lista);
            });

            Papa.parse(arquivoCsv, {
            header: true,
            delimiter: ";",
            skipEmptyLines: true,
            encoding: "ISO-8859-1",
            complete: function (resultado) {
                const linhas = resultado.data;

                // Dois índices: por Id (identidade exacta — o que realmente importa,
                // porque pode haver jogadores diferentes com o mesmo nome) e por nome
                // (fallback para quando o jogador ainda não tem Id no CSV mestre).
                const indice = {};
                const indicePorId = {};
                linhas.forEach((linha, i) => {
                    if (linha.Id) indicePorId[linha.Id] = i;
                    if (!linha.Name) return;
                    const chave = normalizarNomeParaMatch(inverterNome(linha.Name));
                    (indice[chave] = indice[chave] || []).push(i);
                });

                let atualizados = 0, novosComId = 0, novosJogadoresAdicionados = 0;

                // Linhas já escritas por um jogador da equipa nesta run — impede que
                // dois jogadores diferentes com o mesmo nome caiam na mesma linha.
                const linhasUsadas = new Set();

                equipa.forEach(jogadorEquipa => {
                    let idxLinha;
                    const chaveNomeEquipa = normalizarNomeParaMatch(jogadorEquipa.nome);

                    // 1) Identidade por Id — MAS só conta se o nome também bater. Ids
                    //    antigos (gerados só pelo nome, ex: "antonio_0000001") podem já
                    //    ter sido partilhados por engano por DOIS jogadores diferentes
                    //    no CSV mestre; sem esta verificação, o segundo colapsava para
                    //    a linha do primeiro e um jogador desaparecia (perda de dados).
                    if (jogadorEquipa.id && indicePorId[jogadorEquipa.id] !== undefined
                        && !linhasUsadas.has(indicePorId[jogadorEquipa.id])) {
                        const idxCandidato = indicePorId[jogadorEquipa.id];
                        const nomeLinha = linhas[idxCandidato].Name;
                        const nomesBatem = !nomeLinha || normalizarNomeParaMatch(inverterNome(nomeLinha)) === chaveNomeEquipa;
                        if (nomesBatem) idxLinha = idxCandidato;
                        // se não bater, o Id está a ser reutilizado por engano — ignora
                        // este match e segue para o fallback por nome / linha nova, e mais
                        // abaixo é-lhe atribuído um Id novo em vez de continuar a partilhar.
                    }

                    if (idxLinha === undefined) {
                        // 2) Fallback por nome — só linhas livres e SEM Id de outro jogador
                        //    (uma linha já com Id diferente pertence a outra pessoa).
                        const candidatos = (indice[chaveNomeEquipa] || []).filter(i =>
                            !linhasUsadas.has(i) && (!linhas[i].Id || linhas[i].Id === jogadorEquipa.id));
                        if (candidatos.length) {
                            idxLinha = candidatos[0];
                            if (candidatos.length > 1 && jogadorEquipa.team_id) {
                                // 1º tenta clube exacto; só depois similaridade por tokens
                                // (aceita siglas/abreviações sem confundir "Nacional" com
                                // "Nacional da Madeira" — ver clubesSaoSemelhantes).
                                let comClube = candidatos.find(i => slugifyClube(linhas[i].Club) === jogadorEquipa.team_id);
                                if (comClube === undefined) {
                                    comClube = candidatos.find(i => clubesSaoSemelhantes(slugifyClube(linhas[i].Club), jogadorEquipa.team_id));
                                }
                                if (comClube !== undefined) idxLinha = comClube;
                            }
                        }
                    }

                    // 3) Não existe no CSV — adiciona linha nova. O Id nunca é escrito
                    //    por cima de outro: se o Id do .json já pertence a outra linha,
                    //    gera-se um Id novo e único para este jogador.
                    if (idxLinha === undefined) {
                        const idFinal = gerarIdUnicoContra(jogadorEquipa.nome, jogadorEquipa.id, indicePorId);
                        const novaLinha = {
                            Name: reverterNome(jogadorEquipa.nome),
                            Nation: jogadorEquipa.nacionalidade || "",
                            Club: deslugifyClube(jogadorEquipa.team_id) || "",
                            Age: jogadorEquipa.idade || "",
                            Id: idFinal,
                            Pe: jogadorEquipa.pe ?? "",
                            Posicao: jogadorEquipa.posicao ?? "",
                            TAL: jogadorEquipa.TAL ?? "",
                            Valor: jogadorEquipa.valor ?? "",
                            TEC: jogadorEquipa.TEC ?? "",
                            ATA: jogadorEquipa.ATA ?? "",
                            DEF: jogadorEquipa.DEF ?? "",
                            FIS: jogadorEquipa.FIS ?? "",
                            MEN: jogadorEquipa.MEN ?? "",
                            REF: jogadorEquipa.REF ?? "",
                            POS_GK: jogadorEquipa.POS ?? "",
                            AER: jogadorEquipa.AER ?? "",
                            SAI: jogadorEquipa.SAI ?? "",
                            OVER: jogadorEquipa.OVER ?? "",
                        };
                        idxLinha = linhas.length;
                        linhas.push(novaLinha);
                        linhasUsadas.add(idxLinha);
                        indicePorId[idFinal] = idxLinha;
                        novosJogadoresAdicionados++;
                        return;
                    }

                    linhasUsadas.add(idxLinha);

                    const linha = linhas[idxLinha];
                    if (!linha.Id) {
                        // Mesma garantia de unicidade ao preencher o Id de uma linha existente.
                        linha.Id = gerarIdUnicoContra(inverterNome(linha.Name), jogadorEquipa.id, indicePorId);
                        novosComId++;
                    }
                    // Regista o Id para dedup por identidade dentro da mesma run.
                    if (linha.Id) indicePorId[linha.Id] = idxLinha;
                    // O clube do envio (equipa) manda sobre o do CSV mestre — se o jogador
                    // mudou de clube, o team_id da equipa é a fonte da verdade.
                    if (jogadorEquipa.team_id) linha.Club = deslugifyClube(jogadorEquipa.team_id);
                    linha.Pe = jogadorEquipa.pe ?? linha.Pe ?? "";
                    linha.Posicao = jogadorEquipa.posicao ?? linha.Posicao ?? "";
                    linha.TAL = jogadorEquipa.TAL ?? linha.TAL ?? "";
                    linha.Valor = jogadorEquipa.valor ?? linha.Valor ?? "";
                    linha.TEC = jogadorEquipa.TEC ?? linha.TEC ?? "";
                    linha.ATA = jogadorEquipa.ATA ?? linha.ATA ?? "";
                    linha.DEF = jogadorEquipa.DEF ?? linha.DEF ?? "";
                    linha.FIS = jogadorEquipa.FIS ?? linha.FIS ?? "";
                    linha.MEN = jogadorEquipa.MEN ?? linha.MEN ?? "";
                    linha.REF = jogadorEquipa.REF ?? linha.REF ?? "";
                    linha.POS_GK = jogadorEquipa.POS ?? linha.POS_GK ?? "";
                    linha.AER = jogadorEquipa.AER ?? linha.AER ?? "";
                    linha.SAI = jogadorEquipa.SAI ?? linha.SAI ?? "";
                    linha.OVER = jogadorEquipa.OVER ?? linha.OVER ?? "";
                    atualizados++;
                });

                linhas.forEach(linha => {
                    NOVAS_COLUNAS_CSV.forEach(col => { if (linha[col] === undefined) linha[col] = ""; });
                });

                const colunasFinais = [...resultado.meta.fields, ...NOVAS_COLUNAS_CSV.filter(c => !resultado.meta.fields.includes(c))];
                const csvFinal = Papa.unparse(linhas, { delimiter: ";", columns: colunasFinais });

                // Grava em ISO-8859-1 (não UTF-8) para bater certo com a leitura em
                // importarCsv(), que assume ISO-8859-1 — evita mojibake em nomes acentuados
                // quando este CSV actualizado é reimportado no painel.
                const bytesISO = new Uint8Array(csvFinal.length);
                for (let i = 0; i < csvFinal.length; i++) bytesISO[i] = csvFinal.charCodeAt(i) & 0xFF;
                const blob = new Blob([bytesISO], { type: "text/csv;charset=ISO-8859-1" });
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "players_atualizado.csv";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);

                let msg = `Concluído: ${atualizados} jogador(es) actualizado(s) (${novosComId} com Id novo) de ${arquivosJson.length} ficheiro(s) de equipa.`;
                if (novosJogadoresAdicionados) {
                    msg += ` ${novosJogadoresAdicionados} jogador(es) novo(s) adicionado(s) ao CSV (não existiam no ficheiro mestre).`;
                }
                status.textContent = msg;
                },
                error: function (erro) {
                    status.textContent = "Erro ao processar o CSV mestre: " + erro.message;
                }
            });
        })
        .catch(erro => {
            status.textContent = "Erro a ler os .json de equipa: " + erro.message;
        });
}






// Testando Função

function normalizarClubeParaMatch(nome) {
    if (!nome) return "";
    return nome
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")   // separa por espaços (trata "_" do slug também)
        .trim();
}

// Termos genéricos ignorados na comparação (prefixos/siglas comuns e ligações).
const TERMOS_IGNORAR_CLUBE = [
    "fc", "ac", "sc", "cf", "fk", "cr", "tsv", "sd", "ud", "rc", "sad", "cp",
    "sporting", "clube", "club", "atletico", "de", "do", "da"
];

function tokensSignificativosClube(nome) {
    return normalizarClubeParaMatch(nome)
        .split(" ")
        .filter(t => t && !TERMOS_IGNORAR_CLUBE.includes(t));
}

/**
 * Verifica se dois clubes são equivalentes, aceitando siglas/abreviações.
 * Ex: "ac_milan" combina com "Milan"; "tsv_1860_munchen" combina com "1860 Munchen".
 * Usa IGUALDADE de conjuntos de tokens (não substring), por isso "Nacional" NÃO
 * é confundido com "Nacional da Madeira".
 */
function clubesSaoSemelhantes(clubeA, clubeB) {
    if (!clubeA || !clubeB) return false;

    // Igualdade directa (ignorando espaços/pontuação).
    if (normalizarClubeParaMatch(clubeA).replace(/ /g, "") ===
        normalizarClubeParaMatch(clubeB).replace(/ /g, "")) return true;

    const a = tokensSignificativosClube(clubeA);
    const b = tokensSignificativosClube(clubeB);
    if (!a.length || !b.length || a.length !== b.length) return false;

    const setB = new Set(b);
    return a.every(t => setB.has(t)); // mesmos tokens, ordem-independente
}

// NOTA: a versão anterior desta função (definida mais acima, perto de
// lerJsonComoTexto) é a ÚNICA versão activa — este ficheiro tinha aqui uma
// segunda definição (via reatribuição `atualizarCsvComEquipa = function(){...}`)
// que sobrepunha essa e não tinha a protecção contra colisão de Id nem contra
// dois jogadores diferentes caírem na mesma linha. Foi removida (2026) por
// causar perda de jogadores no merge — ver correcção acima que usa
// clubesSaoSemelhantes() como desempate secundário.
