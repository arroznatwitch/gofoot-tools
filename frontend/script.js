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

    // VERIFICAÇÃO INTEGRAL DE TODOS OS CAMPOS DO JOGADOR
    j.completo = !!(
        j.n && j.n.trim() !== "" &&
        j.nat && j.nat.trim() !== "" && j.nat !== "-" &&
        j.c && j.c.trim() !== "" && j.c !== "Sem clube" && j.c !== "-" &&
        j.a &&
        j.pe && j.pe !== "-" &&
        j.p && j.p.trim() !== "" &&
        j.tec && j.ata && j.def && j.fis && j.men &&
        j.v && j.v !== "-" && j.v.trim() !== ""
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
    mapaEdicoes[gerarIdentidade(j)] = { tec: j.tec, ata: j.ata, def: j.def, fis: j.fis, men: j.men, pe: j.pe, v: j.v };
    localStorage.setItem(CHAVE_EDITS, JSON.stringify(mapaEdicoes));
}

function aplicarEdicoesSalvas(j) {
    const salva = mapaEdicoes[gerarIdentidade(j)];
    if (salva) {
        j.tec = salva.tec; j.ata = salva.ata; j.def = salva.def;
        j.fis = salva.fis; j.men = salva.men; j.pe = salva.pe || "-"; j.v = salva.v || "-";
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
function calcularOverallDinamico(j) {
    const tec = parseInt(j.tec) || 0;
    const ata = parseInt(j.ata) || 0;
    const def = parseInt(j.def) || 0;
    const fis = parseInt(j.fis) || 0;
    const men = parseInt(j.men) || 0;

    const category = j.catg || null;
    const positions = (j.p || "").toLowerCase();

    const ehGoleiro = category === "gk" || positions.includes("gk") || positions.includes("gr");
    const ehAtacante = category === "atk" || positions.includes("st") || positions.includes("lw") || positions.includes("rw") || positions.includes("cf") || positions.includes("fwd");
    const ehDefesa = category === "def" || positions.includes("cb") || positions.includes("lb") || positions.includes("rb") || positions.includes("lwb") || positions.includes("rwb");

    if (ehGoleiro) return Math.round(((def * 3) + (fis * 3) + (men * 3) + tec) / 10);
    if (ehAtacante) return Math.round(((tec * 3) + (ata * 3) + (fis * 2) + (men * 2)) / 10);
    if (ehDefesa) return Math.round(((def * 3) + (fis * 3) + (men * 2) + tec + ata) / 10);

    return Math.round(((tec * 3) + (men * 3) + (ata * 2) + def + fis) / 10);
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

function renderizarTabela(dados) {
    const tbody = document.getElementById("playerTableBody");

    if (dados.length === 0) {
        tbody.innerHTML = `<tr><td colspan="15" style="text-align:center; color:#8b949e; padding: 24px;">Nenhum jogador encontrado.</td></tr>`;
        return;
    }

    const linhas = dados.map(j => {
        j.ov = calcularOverallDinamico(j);
        const statusClass = j.completo ? "status-completo" : "status-incompleto";
        const statusTxt = j.completo ? "Completo" : "Incompleto";
        return `
            <tr>
                <td style="font-weight: 600;">${j.n || "-"}</td>
                <td style="color: #8b949e;">${j.nat && j.nat !== "-" ? j.nat.toUpperCase() : "-"}</td>
                <td>${j.c || "-"}</td>
                <td>${j.a || "-"}</td>
                <td style="color: #8b949e; font-size: 13px;">${j.pe || "-"}</td>
                <td style="text-transform: uppercase; font-size: 13px; color: #8b949e;">${j.p || "-"}</td>
                <td class="badge-score ${obterClasseCor(j.ov)}">${j.ov || "-"}</td>
                <td class="badge-score ${obterClasseCor(j.tec)}">${j.tec || "-"}</td>
                <td class="badge-score ${obterClasseCor(j.ata)}">${j.ata || "-"}</td>
                <td class="badge-score ${obterClasseCor(j.def)}">${j.def || "-"}</td>
                <td class="badge-score ${obterClasseCor(j.fis)}">${j.fis || "-"}</td>
                <td class="badge-score ${obterClasseCor(j.men)}">${j.men || "-"}</td>
                <td style="font-weight: 500; color: #58a6ff;">${j.v || "-"}</td>
                <td><span class="status-badge ${statusClass}">${statusTxt}</span></td>
                <td>
                    <button class="btn-edit" onclick="abrirModal(${j._id})" title="Editar">✎</button>
                    <button class="btn-delete" onclick="excluirJogador(${j._id})" title="Excluir">✕</button>
                </td>
            </tr>`;
    }).join("");

    tbody.innerHTML = linhas;
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
        document.getElementById("addValor").value = j.v && j.v !== "-" ? j.v : "";

        const select = document.getElementById("addNat");
        const fallback = document.getElementById("addNatFallback");
        if ([...select.options].some(o => o.value === j.nat)) {
            select.value = j.nat;
        } else if (fallback) {
            fallback.value = j.nat && j.nat !== "-" ? j.nat : "";
        }
    } else {
        titulo.textContent = "Adicionar Novo Jogador";
        btnSalvar.textContent = "Salvar Jogador";
        document.getElementById("playerForm").reset();
    }

    modal.style.display = "flex";
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
        tec: parseInt(document.getElementById("addTec").value),
        ata: parseInt(document.getElementById("addAta").value),
        def: parseInt(document.getElementById("addDef").value),
        fis: parseInt(document.getElementById("addFis").value),
        men: parseInt(document.getElementById("addMen").value),
        v: document.getElementById("addValor").value.trim() || "-"
    };

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
                    tec: null, ata: null, def: null, fis: null, men: null
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

function exportarDados() {
    if (listaJogadores.length === 0) {
        alert("Não há jogadores para exportar.");
        return;
    }

    const listaPronta = listaJogadores.map(j => {
        const { _id, _nLower, _natLower, _cLower, _pLower, _manual, catg, completo, ...limpo } = j;
        limpo.ov = calcularOverallDinamico(j);
        return limpo;
    });

    const conteudoJSON = JSON.stringify(listaPronta, null, 4);
    const blob = new Blob([conteudoJSON], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "fm_players.json";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function exportarDadosFiltrados() {
    if (listaFiltrada.length === 0) {
        alert("Não há jogadores exibidos no filtro atual para exportar.");
        return;
    }

    const listaPronta = listaFiltrada.map(j => {
        const { _id, _nLower, _natLower, _cLower, _pLower, _manual, catg, completo, ...limpo } = j;
        limpo.ov = calcularOverallDinamico(j);
        return limpo;
    });

    const conteudoJSON = JSON.stringify(listaPronta, null, 4);
    const blob = new Blob([conteudoJSON], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;

    const termoBusca = document.getElementById("searchInput").value.trim().toLowerCase().replace(/[^a-z0-9]/g, '_');
    link.download = termoBusca ? `fm_players_filtrado_${termoBusca}.json` : "fm_players_filtrado.json";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function importarDados(event) {
    const arquivo = event.target.files[0];
    if (!arquivo) return;

    const leitor = new FileReader();
    leitor.onload = function (e) {
        try {
            const dadosCarregados = JSON.parse(e.target.result);
            if (!Array.isArray(dadosCarregados)) throw new Error("formato inválido");

            dadosCarregados.forEach(j => {
                j._manual = true;
                marcarStatus(j);
                salvarEdicaoNoStorage(j);
            });

            listaJogadores = listaJogadores.concat(dadosCarregados);
            salvarJogadoresManuaisNoStorage();
            aplicarFiltros();
            alert(`Sucesso! ${dadosCarregados.length} jogadores importados para o painel.`);
        } catch (erro) {
            alert("Não foi possível ler o ficheiro .json. Certifique-se de que é um export compatível.");
        }
    };
    leitor.readAsText(arquivo);
    event.target.value = "";
}