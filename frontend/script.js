// Nomes de nação (inglês, usado nos CSVs, e português, usado no formulário) -> código ISO2.
// Usado só na exportação, para preencher "nacionalidade" no formato que o GoFoot espera.
const ISO_NACOES = {
    "argentina":"ar","armenia":"am","arménia":"am","australia":"au","austrália":"au","austria":"at","áustria":"at",
    "belgium":"be","bélgica":"be","bolivia":"bo","bolívia":"bo","bosnia and herzegovina":"ba","bósnia":"ba",
    "brazil":"br","brasil":"br","bulgaria":"bg","bulgária":"bg","cameroon":"cm","camarões":"cm","canada":"ca","canadá":"ca",
    "chile":"cl","china":"cn","china pr":"cn","colombia":"co","colômbia":"co","costa rica":"cr",
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
    "venezuela":"ve","wales":"gb-wls","gales":"gb-wls","algeria":"dz","argélia":"dz","angola":"ao","albania":"al","albânia":"al",
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

function aplicarFiltros() {
    const termo = document.getElementById("searchInput").value.toLowerCase().trim();
    const soIncompletos = document.getElementById("soIncompletos").checked;

    if (!termo && !soIncompletos) {
        listaFiltrada = listaJogadores;
    } else {
        listaFiltrada = listaJogadores.filter(j => {
            if (soIncompletos && j.completo) return false;
            if (!termo) return true;
            return j._nLower.includes(termo) || j._natLower.includes(termo) ||
                   j._cLower.includes(termo) || j._pLower.includes(termo);
        });
    }
    paginaAtual = 1;
    renderizarPagina();
    atualizarEstatisticas();
}

function atualizarEstatisticas() {
    const completos = listaJogadores.filter(j => j.completo).length;
    document.getElementById("statTotal").textContent = `Total: ${listaJogadores.length.toLocaleString("pt-PT")}`;
    document.getElementById("statCompletos").textContent = `Completos: ${completos.toLocaleString("pt-PT")}`;
    document.getElementById("statIncompletos").textContent = `Incompletos: ${(listaJogadores.length - completos).toLocaleString("pt-PT")}`;
}

function renderizarPagina() {
    const inicio = (paginaAtual - 1) * TAMANHO_PAGINA;
    const pagina = listaFiltrada.slice(inicio, inicio + TAMANHO_PAGINA);
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
            <td style="font-weight: 500; color: #58a6ff;">${j.v || "-"}</td>
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
        tal: parseInt(document.getElementById("addTalento").value) || null,
        v: parseFloat(document.getElementById("addValor").value)
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

            for (const linha of linhas) {
                if (!linha.Name) continue;

                const tagMatch = (linha["Best Rating"] || "").match(/\(([A-Za-z]+)\)/);
                const tag = tagMatch ? tagMatch[1] : null;

                const jogador = {
                    n: linha.Name,
                    nat: linha.Nation || "-",
                    c: linha.Club && linha.Club !== "-" ? linha.Club : "-",
                    a: parseInt(linha.Age) || null,
                    p: linha.Position || "",
                    catg: TAG_CATEGORIA[tag] || null,
                    pe: "-",
                    v: "-",
                    tec: null, ata: null, def: null, fis: null, men: null,
                    ref: null, pos_gk: null, aer: null, sai: null,
                    tal: null
                };

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

// Converte um jogador vindo de um export no formato do GoFoot (nome, idade,
// TEC/ATA/..., posicao como letra) de volta para o formato interno do painel
// (n, a, tec/ata/..., p). Se já vier no formato interno, devolve como está.
// Nota: o export do GoFoot não guarda o clube (não faz parte do formato do
// jogo), por isso essa informação perde-se numa reimportação.
function converterImportGoFoot(j) {
    if (j.n !== undefined && j.p !== undefined) return j; // já é formato interno

    const interno = {
        n: j.nome || "",
        nat: j.nacionalidade || "-",
        c: "-",
        a: j.idade || null,
        pe: PE_LETRA_INVERSO[j.pe] || "-",
        p: j.posicao || "",
        v: (j.valor !== null && j.valor !== undefined) ? j.valor : "-",
        tal: j.TAL ?? null,
    };

    if (j.posicao === "G") {
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
        id: null,
        nome: j.n || null,
        idade: j.a || null,
        nacionalidade: resolverNacaoISO(j.nat),
        numero: null,
        pe: PE_LETRA[j.pe] || null,
        posicao: posicaoGrupo(j),
        TAL: j.tal ?? null,
        salario: null,
        valor: (j.v !== null && j.v !== undefined && j.v !== "-" && !isNaN(j.v)) ? Number(j.v) : null,
        team_id: null,
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
    const conteudoJSON = JSON.stringify(lista, null, 4);
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
    const arquivo = event.target.files[0];
    if (!arquivo) return;

    const leitor = new FileReader();
    leitor.onload = function (e) {
        try {
            const bruto = JSON.parse(e.target.result);
            if (!Array.isArray(bruto)) throw new Error("formato inválido");

            const dadosCarregados = bruto.map(converterImportGoFoot);

            dadosCarregados.forEach(j => {
                j._manual = true;
                marcarStatus(j);
                salvarEdicaoNoStorage(j);
            });

            listaJogadores = listaJogadores.concat(dadosCarregados);
            salvarJogadoresManuaisNoStorage();
            aplicarFiltros();
            alert(`Sucesso! ${dadosCarregados.length} jogadores importados para o painel. (Nota: o clube não vem guardado no export do GoFoot, por isso fica em branco — tens de o preencher outra vez se precisares.)`);
        } catch (erro) {
            alert("Não foi possível ler o ficheiro .json. Certifique-se de que é um export compatível.");
        }
    };
    leitor.readAsText(arquivo);
    event.target.value = "";
}