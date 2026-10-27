"use strict";
// GoFoot Tools: abre um patch do GoFoot, mostra e edita os dados numa cópia em memória e exporta um .gdb.

const POS = ["G", "Z", "LE", "LD", "V", "M", "PE", "PD", "CA"];
const ATTR_LINHA = ["TEC", "ATA", "DEF", "FIS", "MEN"];
const ATTR_GR = ["REF", "POS", "AER", "SAI", "MEN"];

const S = {
    nome: "", meta: null, files: new Map(), clubes: {}, comps: [], paises: [], estadios: [],
    elo: null, imgs: {}, sujos: new Set(), ordem: {}, ligaDe: {}, original: {},
};

const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// ---------- abrir patch ----------
async function abrirFicheiros(lista) {
    const files = new Map();
    for (const f of lista) {
        const p = (f.webkitRelativePath || f.name).split("/");
        files.set(p.length > 1 ? p.slice(1).join("/") : p[0], f);
    }
    await carregar(files);
}

async function abrirGdb(file) {
    const zip = await JSZip.loadAsync(file);
    const files = new Map();
    for (const e of Object.values(zip.files)) {
        if (!e.dir) files.set(e.name.replace(/^[^/]+\/(?=data\/|images\/|patch\.json)/, ""), await e.async("blob"));
    }
    await carregar(files);
}

const lerJson = async (files, p) => (files.has(p) ? JSON.parse(await files.get(p).text()) : null);

async function carregar(files) {
    const meta = await lerJson(files, "patch.json");
    if (!meta) return alert("Isto não parece um patch do GoFoot: falta o patch.json.");
    Object.values(S.imgs).forEach(URL.revokeObjectURL);
    S.files = files; S.meta = meta; S.nome = meta.title || meta.database_id;
    S.sujos = new Set(); S.imgs = {}; S.clubes = {}; S.original = {};
    S.comps = (await lerJson(files, "data/competitions.json"))?.competitions || [];
    S.paises = (await lerJson(files, "data/countries.json"))?.countries || [];
    S.estadios = (await lerJson(files, "data/stadiums.json"))?.stadiums || [];
    for (const p of [...files.keys()].filter((k) => /^data\/clubs\/[^/]+\.json$/.test(k))) {
        const c = await lerJson(files, p);
        S.clubes[c.id] = c;
        S.original[c.id] = JSON.stringify(c);
    }
    for (const [p, f] of files) if (/^images\/clubs\/.+\.png$/.test(p)) S.imgs[p] = URL.createObjectURL(f);
    S.ligaDe = {};
    for (const c of S.comps) if (c.division_level) for (const t of c.teams || []) S.ligaDe[t] = c;
    $("#patch-nome").textContent = `${S.nome} · ${Object.keys(S.clubes).length} clubes`;
    desenharTudo();
}

async function carregarElo() {
    try { S.elo = await (await fetch("elo.json", { cache: "no-cache" })).json(); } catch { S.elo = null; }
}

// ---------- dados derivados ----------
const eloDe = (id) => S.elo?.clubes?.[id] || null;
const escudo = (id) => S.imgs[`images/clubs/${id}.png`] || S.imgs["images/clubs/no-logo.png"] || "";
const liga = (id) => S.ligaDe[id];
const forca = (j) => {
    const at = j.posicao === "G" ? ATTR_GR : ATTR_LINHA;
    const v = at.map((k) => j[k]).filter((x) => typeof x === "number");
    return v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length) : null;
};
function todosJogadores() {
    const out = [];
    for (const c of Object.values(S.clubes)) (c.jogadores || []).forEach((j, i) => out.push({ j, c, i }));
    return out;
}
// reta  elo do jogo = a + b * elo ClubElo, ajustada aos clubes do patch
function retaJogo() {
    const p = Object.values(S.clubes).filter((c) => eloDe(c.id)).map((c) => [eloDe(c.id).elo, c.elo]);
    if (p.length < 3) return null;
    const mx = p.reduce((a, q) => a + q[0], 0) / p.length, my = p.reduce((a, q) => a + q[1], 0) / p.length;
    const sxx = p.reduce((a, q) => a + (q[0] - mx) ** 2, 0);
    if (!sxx) return null;
    const b = p.reduce((a, q) => a + (q[0] - mx) * (q[1] - my), 0) / sxx;
    return (e) => Math.max(0, Math.min(1000, Math.round(my + b * (e - mx))));
}

// ---------- tabelas ----------
function tabela(id, cols, linhas, onClick, limite = 500) {
    const o = S.ordem[id];
    if (o) {
        const col = cols[o.i];
        linhas = [...linhas].sort((a, b) => {
            const x = col.v(a), y = col.v(b);
            return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "pt")) * o.d;
        });
    }
    const total = linhas.length;
    linhas = linhas.slice(0, limite);
    const th = cols.map((c, i) => `<th class="${c.num ? "num" : ""}" data-i="${i}">${c.t}${o?.i === i ? (o.d > 0 ? " ▲" : " ▼") : ""}</th>`).join("");
    const tr = linhas.map((l, n) => `<tr class="${onClick ? "click" : ""}" data-n="${n}">${cols.map((c) => `<td class="${c.num ? "num" : ""}">${c.h ? c.h(l) : esc(c.v(l))}</td>`).join("")}</tr>`).join("");
    const html = `<div class="tablewrap"><table><thead><tr>${th}</tr></thead><tbody>${tr || `<tr><td class="empty" colspan="${cols.length}">Nada para mostrar.</td></tr>`}</tbody></table></div>` +
        (total > limite ? `<p class="sub">A mostrar ${limite} de ${total}. Usa a pesquisa para restringir.</p>` : "");
    return { html, ligar(raiz) {
        raiz.querySelectorAll("th").forEach((h) => (h.onclick = () => {
            const i = +h.dataset.i, a = S.ordem[id];
            S.ordem[id] = { i, d: a && a.i === i ? -a.d : 1 };
            desenhar(abaAtual());
        }));
        if (onClick) raiz.querySelectorAll("tbody tr.click").forEach((r) => (r.onclick = () => onClick(linhas[+r.dataset.n])));
    } };
}

const semPatch = (el) => { el.innerHTML = `<div class="drop"><p>Abre um patch para começar.</p><button class="btn primary" type="button" data-abrir>Abrir patch</button></div>`; $("[data-abrir]", el).onclick = abrirDialogo; };

// ---------- abas ----------
function abaClubes() {
    const el = $("#aba-clubes");
    if (!S.meta) return semPatch(el);
    const ligas = S.comps.filter((c) => c.division_level);
    const f = S.filtro?.clubes || { q: "", l: "" };
    let lista = Object.values(S.clubes).filter((c) => (!f.q || norm(c.nome).includes(norm(f.q))) && (!f.l || liga(c.id)?.id === f.l));
    const t = tabela("clubes", [
        { t: "Clube", v: (c) => c.nome, h: (c) => `<img src="${escudo(c.id)}" alt="">${esc(c.nome)}${S.sujos.has(c.id) ? ' <span class="tag">editado</span>' : ""}` },
        { t: "Liga", v: (c) => liga(c.id)?.division_level ?? 99, h: (c) => esc(liga(c.id)?.name || "-") },
        { t: "Elo", num: 1, v: (c) => eloDe(c.id)?.elo ?? 0, h: (c) => (eloDe(c.id) ? eloDe(c.id).elo : "-") },
        { t: "Origem", v: (c) => eloDe(c.id)?.fonte || "", h: (c) => { const e = eloDe(c.id); return e ? `<span class="tag ${e.fonte === "estimado" ? "est" : ""}">${e.fonte}</span>` : ""; } },
        { t: "Elo jogo", num: 1, v: (c) => c.elo },
        { t: "Reputação", num: 1, v: (c) => c.reputacao },
        { t: "Técnico", v: (c) => c.tecnico?.nome || "" },
        { t: "Jogadores", num: 1, v: (c) => (c.jogadores || []).length },
    ], lista, (c) => dialogoClube(c));
    el.innerHTML = `<h2>Clubes</h2><p class="sub">${Object.keys(S.clubes).length} clubes. Clica num clube para o editar.</p>
        <div class="bar"><input type="search" id="q-clubes" placeholder="Pesquisar clube" value="${esc(f.q)}">
        <select id="l-clubes"><option value="">Todas as ligas</option>${ligas.map((c) => `<option value="${c.id}" ${c.id === f.l ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div>${t.html}`;
    t.ligar(el);
    filtros(el, "clubes", "#q-clubes", "#l-clubes");
}

function filtros(el, nome, q, l) {
    S.filtro = S.filtro || {};
    const aplicar = () => { S.filtro[nome] = { q: $(q, el).value, l: l ? $(l, el).value : "" }; const pos = $(q, el).selectionStart; desenhar(nome); const n = $(q, $(`#aba-${nome}`)); n.focus(); n.setSelectionRange(pos, pos); };
    $(q, el).oninput = aplicar;
    if (l) $(l, el).onchange = aplicar;
}

function abaJogadores() {
    const el = $("#aba-jogadores");
    if (!S.meta) return semPatch(el);
    const todos = todosJogadores();
    if (!todos.length) { el.innerHTML = `<h2>Jogadores</h2><p class="sub">Este patch não tem jogadores nos clubes. Podes adicioná-los na ficha de cada clube.</p>`; return; }
    const f = S.filtro?.jogadores || { q: "", l: "" };
    const lista = todos.filter((x) => (!f.q || norm(x.j.nome).includes(norm(f.q))) && (!f.l || x.j.posicao === f.l));
    const t = tabela("jogadores", [
        { t: "Nome", v: (x) => x.j.nome },
        { t: "Clube", v: (x) => x.c.nome },
        { t: "Pos", v: (x) => POS.indexOf(x.j.posicao) },
        { t: "Idade", num: 1, v: (x) => x.j.idade },
        { t: "Nac", v: (x) => x.j.nacionalidade || "" },
        { t: "Pé", v: (x) => x.j.pe || "" },
        { t: "Força", num: 1, v: (x) => forca(x.j) ?? 0 },
        { t: "TAL", num: 1, v: (x) => x.j.TAL ?? 0 },
        { t: "Contrato", num: 1, v: (x) => x.j.fimContrato ?? 0 },
    ], lista, (x) => dialogoJogador(x.c, x.i));
    el.innerHTML = `<h2>Jogadores</h2><p class="sub">${todos.length} jogadores.</p>
        <div class="bar"><input type="search" id="q-jogadores" placeholder="Pesquisar jogador" value="${esc(f.q)}">
        <select id="l-jogadores"><option value="">Todas as posições</option>${POS.map((p) => `<option ${p === f.l ? "selected" : ""}>${p}</option>`).join("")}</select></div>${t.html}`;
    t.ligar(el);
    filtros(el, "jogadores", "#q-jogadores", "#l-jogadores");
}

function abaLigas() {
    const el = $("#aba-ligas");
    if (!S.meta) return semPatch(el);
    const id = S.filtro?.ligas?.l || S.comps[0]?.id;
    const comp = S.comps.find((c) => c.id === id);
    const pais = (c) => S.paises.find((p) => p.id === c.country_id)?.name || "";
    const lista = (comp?.teams || []).map((t) => S.clubes[t]).filter(Boolean).sort((a, b) => (eloDe(b.id)?.elo ?? 0) - (eloDe(a.id)?.elo ?? 0));
    const t = tabela("ligas", [
        { t: "#", num: 1, v: (c) => lista.indexOf(c) + 1 },
        { t: "Clube", v: (c) => c.nome, h: (c) => `<img src="${escudo(c.id)}" alt="">${esc(c.nome)}` },
        { t: "Elo", num: 1, v: (c) => eloDe(c.id)?.elo ?? 0 },
        { t: "Origem", v: (c) => eloDe(c.id)?.fonte || "" },
        { t: "Reputação", num: 1, v: (c) => c.reputacao },
    ], lista, (c) => dialogoClube(c), 200);
    el.innerHTML = `<h2>Ligas</h2><p class="sub">Competições do patch e os clubes inscritos, por Elo.</p>
        <div class="bar"><select id="l-ligas">${S.comps.map((c) => `<option value="${c.id}" ${c.id === id ? "selected" : ""}>${esc(pais(c))} · ${esc(c.name)} (${(c.teams || []).length})</option>`).join("")}</select></div>${t.html}`;
    t.ligar(el);
    $("#l-ligas", el).onchange = (e) => { S.filtro = S.filtro || {}; S.filtro.ligas = { l: e.target.value }; delete S.ordem.ligas; desenhar("ligas"); };
}

function abaElo() {
    const el = $("#aba-elo");
    if (!S.meta) return semPatch(el);
    if (!S.elo) { el.innerHTML = `<h2>Elo</h2><p class="sub">Não encontrei o elo.json. Gera-o com <code>tools/build_elo.py</code> (ver Wiki).</p>`; return; }
    const m = S.elo.meta, conv = retaJogo();
    const lista = Object.values(S.clubes).filter((c) => eloDe(c.id)).sort((a, b) => eloDe(b.id).elo - eloDe(a.id).elo);
    const t = tabela("elo", [
        { t: "#", num: 1, v: (c) => lista.indexOf(c) + 1 },
        { t: "Clube", v: (c) => c.nome, h: (c) => `<img src="${escudo(c.id)}" alt="">${esc(c.nome)}` },
        { t: "Liga", v: (c) => liga(c.id)?.division_level ?? 99, h: (c) => esc(liga(c.id)?.name || "-") },
        { t: "Elo", num: 1, v: (c) => eloDe(c.id).elo },
        { t: "Origem", v: (c) => eloDe(c.id).fonte, h: (c) => { const e = eloDe(c.id); return `<span class="tag ${e.fonte === "estimado" ? "est" : ""}">${e.fonte}</span>${e.ref ? " " + esc(e.ref) : ""}`; } },
        { t: "Elo jogo atual", num: 1, v: (c) => c.elo },
        { t: "Equivalente", num: 1, v: (c) => (conv ? conv(eloDe(c.id).elo) : 0), h: (c) => (conv ? conv(eloDe(c.id).elo) : "-") },
    ], lista, (c) => dialogoClube(c), 300);
    el.innerHTML = `<h2>Elo</h2><p class="sub">Elo ClubElo dos clubes do patch. Os estimados vêm da divisão e da reputação (ver Wiki).</p>
        <div class="stats"><div><b>${m.reais}</b>no ClubElo</div><div><b>${m.estimados}</b>estimados</div><div><b>${esc(m.gerado)}</b>data dos dados</div></div>
        <div class="bar"><button class="btn" id="aplicar-elo" ${conv ? "" : "disabled"}>Aplicar equivalente no jogo à cópia de trabalho</button></div>${t.html}`;
    t.ligar(el);
    $("#aplicar-elo", el).onclick = () => {
        if (!confirm("Isto muda o campo elo de todos os clubes na cópia de trabalho (o patch original não é tocado). Continuar?")) return;
        for (const c of lista) { c.elo = conv(eloDe(c.id).elo); S.sujos.add(c.id); }
        desenharTudo();
    };
}

function abaExportar() {
    const el = $("#aba-exportar");
    if (!S.meta) return semPatch(el);
    const p = validar();
    const erros = p.filter((x) => x.n === "erro").length, avisos = p.length - erros;
    el.innerHTML = `<h2>Validar e exportar</h2><p class="sub">Verifica o patch e gera um .gdb novo. O patch original não é alterado.</p>
        <div class="stats"><div><b>${S.sujos.size}</b>clubes editados</div><div><b class="${erros ? "err" : "ok"}">${erros}</b>erros</div><div><b>${avisos}</b>avisos</div></div>
        <div class="bar"><button class="btn primary" id="exp">Exportar .gdb</button></div>
        ${p.length ? `<ul class="issues">${p.slice(0, 300).map((x) => `<li><span class="${x.n === "erro" ? "err" : "warn"}">${x.n}</span> · ${esc(x.t)}</li>`).join("")}</ul>${p.length > 300 ? `<p class="sub">${p.length - 300} problemas ocultos.</p>` : ""}` : `<p class="ok">Nenhum problema encontrado.</p>`}`;
    $("#exp", el).onclick = exportar;
}

// ---------- validação ----------
function validar() {
    const out = [], add = (n, t) => out.push({ n, t });
    const emComp = new Set(S.comps.flatMap((c) => c.teams || []));
    for (const c of Object.values(S.clubes)) {
        const q = `${c.nome}`;
        if (!c.nome) add("erro", `${c.id}: sem nome`);
        if (!(c.reputacao >= 0 && c.reputacao <= 100)) add("erro", `${q}: reputação fora de 0 a 100`);
        if (!(c.elo >= 0 && c.elo <= 1000)) add("erro", `${q}: elo fora de 0 a 1000`);
        if (!emComp.has(c.id)) add("aviso", `${q}: não está inscrito em nenhuma competição`);
        if (!S.imgs[`images/clubs/${c.id}.png`]) add("aviso", `${q}: sem escudo`);
        if (!S.estadios.some((e) => e.id === c.stadium_id)) add("aviso", `${q}: estádio '${c.stadium_id}' não existe`);
        const js = c.jogadores || [], nums = new Set();
        if (js.length && js.filter((j) => j.posicao === "G").length < 2) add("aviso", `${q}: menos de 2 guarda-redes`);
        js.forEach((j) => {
            const w = `${q} / ${j.nome || "?"}`;
            if (!j.nome) add("erro", `${q}: jogador sem nome`);
            if (!POS.includes(j.posicao)) add("erro", `${w}: posição inválida`);
            if (!(j.idade >= 15 && j.idade <= 45)) add("erro", `${w}: idade fora de 15 a 45`);
            for (const k of [...ATTR_LINHA, ...ATTR_GR, "TAL"]) if (j[k] != null && !(j[k] >= 1 && j[k] <= 99)) add("erro", `${w}: ${k} fora de 1 a 99`);
            if (j.numero != null) { if (nums.has(j.numero)) add("erro", `${w}: número ${j.numero} repetido`); nums.add(j.numero); }
        });
    }
    for (const c of S.comps) for (const t of c.teams || []) if (!S.clubes[t]) add("erro", `${c.name}: clube '${t}' não existe`);
    return out;
}

// ---------- exportar ----------
async function exportar() {
    const zip = new JSZip(), raiz = zip.folder(S.meta.database_id || "patch");
    for (const [p, f] of S.files) raiz.file(p, f);
    for (const id of S.sujos) raiz.file(`data/clubs/${id}.json`, JSON.stringify(S.clubes[id], null, "\t"));
    const blob = await zip.generateAsync({ type: "blob", compression: "DEFLATE" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${S.meta.database_id || "patch"}_editado.gdb`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

// ---------- diálogos de edição ----------
const dlg = $("#dlg"), form = $("#dlg-form");
function campo(k, rot, v, tipo = "text", extra = "") {
    return `<label class="${extra}">${rot}<input name="${k}" type="${tipo}" value="${esc(v ?? "")}"></label>`;
}
function marcar(c) { S.sujos.add(c.id); }

function dialogoClube(c) {
    const js = c.jogadores || [];
    form.innerHTML = `<h3>${esc(c.nome)}</h3><div class="grid">
        ${campo("nome", "Nome", c.nome, "text", "wide")}
        ${campo("reputacao", "Reputação (0-100)", c.reputacao, "number")}
        ${campo("elo", "Elo no jogo (0-1000)", c.elo, "number")}
        ${campo("corPrimaria", "Cor primária", c.corPrimaria, "color")}
        ${campo("corSecundaria", "Cor secundária", c.corSecundaria, "color")}
        ${campo("tecnico", "Técnico", c.tecnico?.nome, "text", "wide")}</div>
        <h3 style="margin-top:18px">Plantel (${js.length})</h3>
        ${js.length ? `<div class="tablewrap" style="max-height:240px;overflow:auto"><table><tbody>${js.map((j, i) => `<tr class="click" data-i="${i}"><td>${esc(j.nome)}</td><td>${esc(j.posicao)}</td><td class="num">${j.idade}</td><td class="num">${forca(j) ?? ""}</td></tr>`).join("")}</tbody></table></div>` : `<p class="sub">Sem jogadores.</p>`}
        <div class="actions"><button class="btn left" type="button" id="novo-j">Adicionar jogador</button><button class="btn" value="x">Cancelar</button><button class="btn primary" value="ok">Guardar</button></div>`;
    const guardar = (fd) => {
        c.nome = fd.get("nome").trim() || c.nome;
        c.reputacao = +fd.get("reputacao"); c.elo = +fd.get("elo");
        c.corPrimaria = fd.get("corPrimaria"); c.corSecundaria = fd.get("corSecundaria");
        if (c.tecnico) c.tecnico.nome = fd.get("tecnico"); else if (fd.get("tecnico")) c.tecnico = { nome: fd.get("tecnico") };
        if (JSON.stringify(c) !== S.original[c.id]) marcar(c);
    };
    const ir = (i) => () => { guardar(new FormData(form)); irPara(() => dialogoJogador(c, i)); };
    form.querySelectorAll("tr.click").forEach((r) => (r.onclick = ir(+r.dataset.i)));
    $("#novo-j", form).onclick = ir(-1);
    abrir(guardar);
}

function dialogoJogador(c, i) {
    const novo = i < 0, j = novo ? { nome: "", posicao: "M", idade: 22, pe: "D", nacionalidade: "pt" } : c.jogadores[i];
    const num = (k, r) => campo(k, r, j[k], "number");
    form.innerHTML = `<h3>${novo ? "Novo jogador" : esc(j.nome)} · ${esc(c.nome)}</h3><div class="grid">
        ${campo("nome", "Nome", j.nome, "text", "wide")}
        <label>Posição<select name="posicao">${POS.map((p) => `<option ${p === j.posicao ? "selected" : ""}>${p}</option>`).join("")}</select></label>
        ${num("idade", "Idade")}
        <label>Pé<select name="pe">${["D", "E", "A"].map((p) => `<option ${p === j.pe ? "selected" : ""}>${p}</option>`).join("")}</select></label>
        ${campo("nacionalidade", "Nacionalidade", j.nacionalidade)}
        ${num("numero", "Número")}${num("fimContrato", "Fim do contrato")}
        ${num("TEC", "TEC")}${num("ATA", "ATA")}${num("DEF", "DEF")}${num("FIS", "FIS")}${num("MEN", "MEN")}
        ${num("REF", "REF")}${num("POS", "POS")}${num("AER", "AER")}${num("SAI", "SAI")}${num("TAL", "TAL")}</div>
        <div class="actions">${novo ? "" : `<button class="btn left" type="button" id="apagar-j">Apagar</button>`}<button class="btn" value="x">Cancelar</button><button class="btn primary" value="ok">Guardar</button></div>`;
    const apagar = $("#apagar-j", form);
    if (apagar) apagar.onclick = () => { if (confirm(`Apagar ${j.nome}?`)) { c.jogadores.splice(i, 1); marcar(c); dlg.close(); desenharTudo(); } };
    abrir((fd) => {
        const o = { ...j };
        for (const [k, v] of fd) {
            if (["nome", "posicao", "pe", "nacionalidade"].includes(k)) { if (v !== "") o[k] = v.trim(); else delete o[k]; }
            else if (v === "") delete o[k]; else o[k] = +v;
        }
        if (!o.nome) return;
        if (novo) { c.jogadores = c.jogadores || []; c.jogadores.push(o); } else c.jogadores[i] = o;
        marcar(c);
    });
}

const irPara = (fn) => { dlg.close(); fn(); };

function abrir(aoGuardar) {
    form.onsubmit = (e) => {
        e.preventDefault();
        if (e.submitter?.value === "ok") { aoGuardar(new FormData(form)); desenharTudo(); }
        dlg.close();
    };
    dlg.showModal();
}

// ---------- estrutura ----------
const ABAS = { clubes: abaClubes, jogadores: abaJogadores, ligas: abaLigas, elo: abaElo, exportar: abaExportar };
const abaAtual = () => $("#tabs .on").dataset.aba;
const desenhar = (n) => ABAS[n]?.();
const desenharTudo = () => { for (const n of Object.keys(ABAS)) if (!$(`#aba-${n}`).hidden) desenhar(n); };

function trocar(nome) {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.aba === nome));
    document.querySelectorAll("main > section").forEach((s) => (s.hidden = s.id !== `aba-${nome}`));
    desenhar(nome);
    if (location.hash !== `#${nome}`) history.replaceState(null, "", `#${nome}`);
}

function abrirDialogo() {
    const d = $("#dlg"); const f = $("#dlg-form");
    f.innerHTML = `<h3>Abrir patch</h3><p class="sub">Escolhe a pasta do patch ou um ficheiro .gdb.</p>
        <div class="actions"><button class="btn left" value="x">Cancelar</button><button class="btn" type="button" id="o-gdb">Ficheiro .gdb</button><button class="btn primary" type="button" id="o-pasta">Pasta do patch</button></div>`;
    $("#o-pasta", f).onclick = () => irPara(() => $("#in-pasta").click());
    $("#o-gdb", f).onclick = () => irPara(() => $("#in-gdb").click());
    f.onsubmit = null; d.showModal();
}

document.querySelectorAll("#tabs button").forEach((b) => (b.onclick = () => trocar(b.dataset.aba)));
$("#btn-abrir").onclick = abrirDialogo;
$("#in-pasta").onchange = (e) => { if (e.target.files.length) abrirFicheiros(e.target.files); e.target.value = ""; };
$("#in-gdb").onchange = (e) => { if (e.target.files[0]) abrirGdb(e.target.files[0]); e.target.value = ""; };
window.addEventListener("beforeunload", (e) => { if (S.sujos.size) { e.preventDefault(); e.returnValue = ""; } });
window.gofoot = { carregar, S }; // usado nos testes

carregarElo().then(() => trocar(["clubes", "jogadores", "ligas", "elo", "exportar", "wiki"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "clubes"));
