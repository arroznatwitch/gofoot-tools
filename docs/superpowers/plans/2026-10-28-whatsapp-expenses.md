# Finanças pessoais via WhatsApp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registar despesas por WhatsApp (texto/foto) e vê-las num dashboard privado com resumos e gráficos, a custo zero.

**Architecture:** Um único Cloudflare Worker (TypeScript) recebe o webhook da Meta, analisa mensagens (regras para texto, Gemini para fotos), grava em D1 e serve o dashboard e a API JSON atrás de login por palavra-passe.

**Tech Stack:** TypeScript, Cloudflare Workers + D1, Hono (routing), Vitest com `@cloudflare/vitest-pool-workers`, Chart.js (CDN, versão fixa) no dashboard, Meta WhatsApp Cloud API, Gemini API (plano gratuito).

**Spec:** `docs/superpowers/specs/2026-10-28-whatsapp-expenses-design.md`

**Código vive num repositório novo**, `H:\expenses-whatsapp` (não dentro de `gofoot-tools`). Os caminhos abaixo são relativos a essa pasta.

## Global Constraints

- Custo zero: só planos gratuitos (Cloudflare, Meta número de teste, Gemini free). Confirmar limites atuais antes da Task 9.
- Moeda única EUR; valores guardados em cêntimos (`amount_cents INTEGER`).
- Interface e respostas em pt-PT; fuso `Europe/Lisbon`.
- Categorias iniciais: Alimentação, Transportes, Casa, Saúde, Lazer, Compras, Outros.
- Só o número em `ALLOWED_SENDER` é processado; webhook exige assinatura HMAC-SHA256 válida (`X-Hub-Signature-256`, segredo `META_APP_SECRET`).
- Cookie de sessão `HttpOnly; Secure; SameSite=Strict`; palavra-passe só como hash (PBKDF2 via WebCrypto) em segredo `PASSWORD_HASH`.
- Fotos de recibos nunca são guardadas; apagadas da memória após leitura.
- `wa_message_id` único: reentregas do webhook não duplicam despesas.
- Segredos só em `wrangler secret`/`.dev.vars` (gitignored), nunca no repositório.

## Review Focus

- Mesmo webhook entregue duas vezes → uma só despesa (Task 5).
- Texto sem valor ("olá", "ontem") → nada gravado e resposta com exemplo (Tasks 2, 5).
- Formatos de valor "12,50", "12.50€", "€12,5", "1.234,56" → centimos corretos (Task 2).
- "ontem", "dd/mm", "dd/mm/aaaa" e datas futuras ou inválidas ("31/02") → data válida ou hoje (Task 2).
- Gemini indisponível/resposta inválida → despesa `a_rever`, utilizador avisado (Task 6).

---

### Task 1: Scaffold, schema e camada de dados

**Files:**
- Create: `package.json`, `wrangler.toml`, `tsconfig.json`, `vitest.config.ts`, `.gitignore`, `.dev.vars.example`
- Create: `migrations/0001_init.sql`, `src/db.ts`, `src/types.ts`
- Test: `test/db.test.ts`

**Interfaces:**
- Produces (`src/types.ts`): `type Category = string`; `type Expense = { id:number; waMessageId:string|null; amountCents:number; category:string; spentOn:string /*YYYY-MM-DD*/; description:string; merchant:string|null; source:'text'|'photo'|'manual'; status:'ok'|'a_rever'; createdAt:string }`; `type NewExpense = Omit<Expense,'id'|'createdAt'>`.
- Produces (`src/db.ts`): `insertExpense(db:D1Database, e:NewExpense): Promise<Expense|null>` (null se `waMessageId` duplicado); `updateExpense(db,id,patch:Partial<NewExpense>): Promise<Expense|null>`; `deleteExpense(db,id): Promise<boolean>`; `deleteLastExpense(db): Promise<Expense|null>`; `listExpenses(db,{month:string /*YYYY-MM*/,status?:'a_rever'}): Promise<Expense[]>`; `monthSummary(db, month): Promise<{totalCents:number; count:number; prevTotalCents:number; byCategory:{category:string;totalCents:number}[]; byDay:{day:string;totalCents:number}[]}>`; `getCategories(db): Promise<{name:string;keywords:string[]}[]>`.

- [ ] **Step 1:** `npm init`, instalar `hono`, `wrangler`, `vitest`, `@cloudflare/vitest-pool-workers`, `typescript`; criar `wrangler.toml` com binding `DB`, `compatibility_date` atual; criar repo git em `H:\expenses-whatsapp`.
- [ ] **Step 2:** `migrations/0001_init.sql` com tabelas `expenses` (colunas do spec, `wa_message_id UNIQUE`), `categories(name PRIMARY KEY, keywords TEXT)` semeada com as 7 categorias e palavras-chave pt (ex.: Alimentação: `almoço,jantar,café,restaurante,supermercado,pingo doce,continente`), `sessions(token_hash PRIMARY KEY, expires_at)`; o vitest-pool aplica as migrações.
- [ ] **Step 3: Write failing tests** em `test/db.test.ts`: `insertExpense` duas vezes com o mesmo `waMessageId` devolve objeto e depois `null`; `monthSummary` de 3 despesas em 2 categorias dá `totalCents` correto, `byCategory` ordenado desc e `prevTotalCents` do mês anterior; `deleteLastExpense` apaga a mais recente; `listExpenses` com `status:'a_rever'` filtra.
- [ ] **Step 4:** Run `npx vitest run test/db.test.ts` → FAIL (módulo não existe).
- [ ] **Step 5:** Implementar `src/db.ts` com as assinaturas acima (SQL parametrizado, sem concatenação).
- [ ] **Step 6:** Run `npx vitest run` → PASS.
- [ ] **Step 7:** Commit `feat: scaffold project, schema and data layer`.

### Task 2: Parser de texto

**Files:** Create `src/parser.ts`; Test `test/parser.test.ts`

**Interfaces:**
- Consumes: `getCategories` resultado (passado como argumento, a função é pura).
- Produces: `parseExpenseText(text:string, today:string /*YYYY-MM-DD*/, categories:{name:string;keywords:string[]}[]): ParsedExpense | null` onde `ParsedExpense = { amountCents:number; category:string; spentOn:string; description:string; confident:boolean }`. `confident=false` quando a categoria caiu em "Outros" por falta de palavra-chave.

- [ ] **Step 1: Write failing tests** (tabela de casos): `"almoço 12,50"`→1250/Alimentação; `"12.5€ café"`→1250; `"€3 uber"`; `"1.234,56 renda"`→123456; `"gasolina 40 ontem"` com today=2026-10-28 → `2026-10-27`; `"cinema 9 15/10"`→`2026-10-15`; `"x 5 31/02"`→hoje; `"olá"`, `""`, `"ontem"` → `null`; `"jantar 20 20/10/2027"` (futuro) → hoje; `"qualquer coisa 7"` → Outros, `confident:false`.
- [ ] **Step 2:** Run `npx vitest run test/parser.test.ts` → FAIL.
- [ ] **Step 3:** Implementar `parseExpenseText`: extrair o primeiro número monetário por regex (separador de milhar `.`, decimal `,` ou `.`), depois a data (palavras "hoje/ontem/anteontem", `dd/mm[/aaaa]` validada com `Date`), o resto é `description`; categoria pela primeira palavra-chave (normalizada sem acentos, minúsculas) que ocorre.
- [ ] **Step 4:** Run → PASS. Step 5: Commit `feat: text expense parser`.

### Task 3: Autenticação

**Files:** Create `src/auth.ts`; Test `test/auth.test.ts`

**Interfaces:**
- Consumes: tabela `sessions` (Task 1).
- Produces: `hashPassword(pw:string, salt?:Uint8Array): Promise<string>` (formato `pbkdf2$iter$salt$hash`); `verifyPassword(pw, stored): Promise<boolean>`; `createSession(db): Promise<string /*token*/>` (guarda só `sha256(token)`, expira em 30 dias); `validateSession(db, token): Promise<boolean>`; `rateLimit(db or KV-free in-table, ip): Promise<boolean>` (máx. 5 falhas/15 min por IP, tabela `login_attempts` adicionada em `migrations/0002_login_attempts.sql`); middleware Hono `requireAuth` (401 JSON em `/api/*`, redirect `/login` nas páginas).

- [ ] **Step 1: Write failing tests:** hash≠palavra-passe e verifica; palavra-passe errada → false; sessão válida → true, token desconhecido → false, sessão expirada → false; 6.ª tentativa falhada do mesmo IP → bloqueada.
- [ ] **Step 2:** Run → FAIL. Step 3: Implementar com WebCrypto (`PBKDF2`, 100000 iterações, SHA-256), comparação em tempo constante. Step 4: Run → PASS. Step 5: Commit `feat: password auth and sessions`.

### Task 4: Cliente WhatsApp

**Files:** Create `src/whatsapp.ts`; Test `test/whatsapp.test.ts`

**Interfaces:**
- Produces: `verifySignature(rawBody:string, header:string|null, appSecret:string): Promise<boolean>`; `sendText(env, to:string, body:string): Promise<void>` (POST Graph API `/{PHONE_NUMBER_ID}/messages`); `downloadMedia(env, mediaId:string): Promise<{bytes:ArrayBuffer; mimeType:string}>`. Tipo `Env` em `src/types.ts` com `DB, META_APP_SECRET, META_VERIFY_TOKEN, META_ACCESS_TOKEN, PHONE_NUMBER_ID, ALLOWED_SENDER, GEMINI_API_KEY, PASSWORD_HASH`.

- [ ] **Step 1: Write failing tests:** assinatura correta (HMAC calculado no teste) → true; corpo alterado, cabeçalho ausente ou sem prefixo `sha256=` → false; `sendText` faz `fetch` mockado com `Authorization: Bearer` e corpo `{messaging_product:'whatsapp', to, text:{body}}`.
- [ ] **Step 2:** Run → FAIL. Step 3: Implementar (comparação em tempo constante). Step 4: Run → PASS. Step 5: Commit `feat: whatsapp client`.

### Task 5: Webhook (texto, apagar, idempotência)

**Files:** Create `src/webhook.ts`, `src/index.ts` (app Hono e export default); Test `test/webhook.test.ts`

**Interfaces:**
- Consumes: `parseExpenseText` (T2), `insertExpense`, `deleteLastExpense`, `getCategories` (T1), `verifySignature`, `sendText` (T4).
- Produces: `GET /webhook` (handshake: devolve `hub.challenge` se `hub.verify_token === META_VERIFY_TOKEN`, senão 403); `POST /webhook` (devolve sempre 200 rapidamente após processar, 401 só se assinatura inválida); `handleMessage(env, msg): Promise<void>`; formato de confirmação `"✔ 12,50 € · Alimentação · 28/10"`, e `"?"` quando `status='a_rever'`: `"⚠ 12,50 € · Outros · 28/10 (a rever no dashboard)"`.

- [ ] **Step 1: Write failing tests** (payloads Meta simulados, `fetch` mockado): assinatura inválida → 401 e nada gravado; remetente ≠ `ALLOWED_SENDER` → 200, nada gravado, nenhuma resposta; texto "almoço 12,50" → despesa gravada com `wa_message_id` e resposta de confirmação enviada; **mesmo payload duas vezes → 1 linha e 1 resposta**; "olá" → nada gravado e resposta com exemplo `"Ex.: almoço 12,50 ontem"`; "apagar" → apaga a última e responde; "apagar" sem despesas → resposta "Nada para apagar."; handshake GET correto/errado.
- [ ] **Step 2:** Run → FAIL. Step 3: Implementar; `today` calculado em `Europe/Lisbon`; despesa com `confident=false` grava `status='a_rever'`. Step 4: Run → PASS. Step 5: Commit `feat: whatsapp webhook for text messages`.

### Task 6: Fotos de recibos (Gemini)

**Files:** Create `src/vision.ts`; Modify `src/webhook.ts` (ramo `image`); Test `test/vision.test.ts`, `test/webhook.test.ts`

**Interfaces:**
- Consumes: `downloadMedia` (T4), `Env.GEMINI_API_KEY`.
- Produces: `parseReceiptImage(env, image:{bytes:ArrayBuffer; mimeType:string}, today:string, categories:string[]): Promise<{amountCents:number; category:string; spentOn:string; merchant:string|null; description:string} | null>` — `null` em falha de rede, HTTP não-OK, JSON inválido ou valor ≤ 0.

- [ ] **Step 1: Write failing tests** (fetch mockado para a API Gemini): resposta JSON válida → campos corretos, categoria fora da lista → "Outros"; HTTP 429, JSON malformado, `amount` negativo → `null`; no webhook, mensagem `image` com Gemini ok → despesa `source='photo'`, `status='ok'`; com `null` → despesa não é criada com dados inventados: grava `amountCents=0`, `status='a_rever'`, `source='photo'` e responde "Não consegui ler o recibo; fica em 'a rever'."
- [ ] **Step 2:** Run → FAIL. Step 3: Implementar com pedido `generateContent` do Gemini a pedir JSON estruturado (`responseMimeType: application/json`, esquema com os 5 campos); modelo Flash gratuito (confirmar o nome atual na documentação). Imagem apenas em memória. Step 4: Run → PASS. Step 5: Commit `feat: receipt photo parsing with Gemini`.

### Task 7: API do dashboard

**Files:** Create `src/api.ts`; Modify `src/index.ts`; Test `test/api.test.ts`

**Interfaces:**
- Consumes: `requireAuth`, `verifyPassword`, `createSession` (T3), funções de `db.ts` (T1).
- Produces: `POST /api/login {password}` → define cookie `session`; `POST /api/logout`; `GET /api/summary?month=YYYY-MM` → resultado de `monthSummary`; `GET /api/expenses?month=&status=` ; `POST /api/expenses` (manual); `PATCH /api/expenses/:id`; `DELETE /api/expenses/:id`. Validação: `month` formato `YYYY-MM`, `amountCents` inteiro > 0, `spentOn` data válida, `category` existente; erro 400 com mensagem.

- [ ] **Step 1: Write failing tests:** sem cookie → 401 em todas as rotas `/api/*` exceto login; login errado → 401; login certo → cookie com `HttpOnly`, `Secure`, `SameSite=Strict`; `summary` com `month=abc` → 400; CRUD completo; PATCH que muda estado para `ok` tira de "a rever".
- [ ] **Step 2:** Run → FAIL. Step 3: Implementar. Step 4: Run → PASS. Step 5: Commit `feat: dashboard API`.

### Task 8: Páginas do dashboard

**Files:** Create `public/login.html`, `public/index.html`, `public/app.js`, `public/style.css`; Modify `wrangler.toml` (`[assets]`), `src/index.ts` (servir páginas; `/` exige sessão, `/login` pública); Test `test/pages.test.ts`

**Interfaces:**
- Consumes: endpoints da Task 7.
- Produces: `/login` (formulário); `/` com seletor de mês, cartões (total, vs. mês anterior, nº de despesas), donut por categoria, barras por dia (Chart.js de cdnjs com versão fixa e SRI), tabela com editar/apagar/adicionar e filtro "a rever"; layout responsivo para telemóvel; tema claro/escuro.

- [ ] **Step 1: Write failing tests:** `GET /` sem sessão → redirect 302 para `/login`; com sessão → 200 HTML; `GET /login` → 200.
- [ ] **Step 2:** Run → FAIL. Step 3: Implementar páginas; todo o texto inserido via `textContent` (nunca `innerHTML` com dados de despesas, para evitar XSS vindo de descrições do WhatsApp). Step 4: Run → PASS.
- [ ] **Step 5:** Verificação manual com `npx wrangler dev`: criar despesas via API, abrir o dashboard, confirmar gráficos, edição, mobile (largura 375px) e tema escuro.
- [ ] **Step 6:** Commit `feat: dashboard pages`.

### Task 9: Deploy e ligação à Meta/Gemini

**Files:** Create `README.md` (passo a passo); Modify `wrangler.toml`

- [ ] **Step 1 (feito por ti, com guia):** criar conta Cloudflare gratuita e `wrangler login`; `wrangler d1 create expenses` e colocar o `database_id` em `wrangler.toml`; `wrangler d1 migrations apply expenses --remote`.
- [ ] **Step 2:** `wrangler secret put` para cada segredo (gera-se `PASSWORD_HASH` com um script `npm run hash-password`).
- [ ] **Step 3 (feito por ti):** app Meta for Developers → WhatsApp → número de teste; adicionar o teu número como destinatário; criar token de longa duração (utilizador de sistema); configurar webhook com a URL do Worker e `META_VERIFY_TOKEN`, subscrever `messages`. Chave Gemini em Google AI Studio.
- [ ] **Step 4:** `wrangler deploy`; verificar os limites gratuitos vigentes e anotá-los no README.
- [ ] **Step 5: Verificação ponta a ponta:** enviar "almoço 12,50" → resposta ✔ e linha no dashboard; reenviar via webhook retry não duplica; enviar foto de recibo real; "apagar"; login errado 6 vezes bloqueia.
- [ ] **Step 6:** Commit `docs: deployment guide`.
