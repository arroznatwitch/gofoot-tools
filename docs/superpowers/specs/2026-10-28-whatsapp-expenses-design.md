# Finanças pessoais via WhatsApp — Design

Data: 2026-10-28 · Estado: para revisão

## Objetivo
Registar despesas enviando texto ou foto de recibo por WhatsApp; a app extrai valor, categoria e data e mostra tudo num dashboard privado, protegido por palavra-passe, com resumos mensais e gráficos. Uso pessoal (uma pessoa), **custo zero**.

## Âmbito
**Dentro:** entrada por WhatsApp, análise de texto e fotos, confirmação por resposta, dashboard com login, resumo mensal, gráficos, edição/remoção de despesas, fila "a rever".
**Fora (v1):** multiutilizador, várias moedas, orçamentos, receitas, exportação.

## Pressupostos
- Moeda única: EUR. Interface em português (pt-PT).
- Categorias iniciais (editáveis): Alimentação, Transportes, Casa, Saúde, Lazer, Compras, Outros.
- Data por omissão: hoje (fuso Europe/Lisbon).

## Arquitetura
Tudo corre em **Cloudflare Workers** (plano gratuito) com base **D1** (SQLite). Sem servidor próprio, sem túnel. Os limites do plano gratuito devem ser confirmados antes de construir.

```
WhatsApp (Meta Cloud API, número de teste)
   │ webhook HTTPS
   ▼
Worker ── verifica assinatura + número remetente
   ├─ texto  → parser por regras ─┐
   ├─ foto   → Gemini (visão)    ─┼→ D1 (expenses)
   │                              │
   └─ resposta de confirmação ←───┘
Worker (mesma app) ── /login, /api/*, páginas do dashboard
```

### Unidades
| Unidade | Função | Depende de |
|---|---|---|
| `webhook` | Valida pedido da Meta (assinatura HMAC, remetente permitido), encaminha mensagens | parser, vision, db, whatsapp |
| `parser` | Texto → `{amount, category, date, description}` ou `null`; função pura | — |
| `vision` | Foto → mesmos campos + loja, via Gemini | API Gemini |
| `whatsapp` | Descarrega media, envia respostas | API Meta |
| `db` | Acesso a D1 (CRUD de despesas, agregados mensais) | D1 |
| `auth` | Login por palavra-passe (hash), sessão por cookie | db |
| `dashboard` | Páginas + API JSON para resumo, gráficos, edição | auth, db |

## Fluxo de dados
1. Mensagem chega ao webhook; assinatura e número remetente são verificados, caso contrário 401/ignora.
2. Texto: o parser tira o valor ("12,50", "12.5€"), data relativa ("ontem", "dd/mm") e categoria por palavras-chave. Foto: descarrega, envia ao Gemini, apaga a imagem logo após leitura (nada guardado).
3. Se valor e categoria têm confiança → estado `ok`; senão estado `a_rever`, mas guarda sempre a despesa quando há valor.
4. Resposta no WhatsApp: "✔ 12,50 € · Alimentação · 28/10". Comando "apagar" anula a última despesa.
5. Idempotência: o id da mensagem da Meta é único em D1, evitando duplicados nas reentregas do webhook.

## Dados
`expenses(id, wa_message_id UNIQUE, amount_cents, category, spent_on, description, merchant, source[text|photo|manual], status[ok|a_rever], created_at)`
`categories(name, keywords)` · `sessions(token_hash, expires_at)` · palavra-passe como hash em segredo do Worker.

## Dashboard
- Login com palavra-passe, cookie HttpOnly/Secure/SameSite=Strict, limite de tentativas.
- Resumo do mês: total, comparação com mês anterior, nº de despesas.
- Gráficos: por categoria (donut) e evolução diária (barras); navegação entre meses.
- Tabela: editar, apagar, adicionar à mão; filtro "a rever".

## Erros
- Gemini falha/limite diário: guarda despesa `a_rever` sem dados e avisa no WhatsApp.
- Mensagem sem valor reconhecível: responde com exemplo de formato; nada é gravado.
- Remetente não autorizado: ignorado em silêncio.

## Testes
- Unitários exaustivos do `parser` (formatos de valor, datas, categorias, lixo).
- Integração do webhook com payloads simulados (assinatura inválida, duplicado, texto, foto com Gemini simulado).
- Testes de auth (sessão, tentativas) e dos agregados mensais.

## Riscos
- Número de teste da Meta limita a 5 destinatários e o token pode precisar de renovação; usar token de longa duração de utilizador de sistema.
- Limites do Gemini gratuito; mitigado pelo estado `a_rever`.
- Limites do plano gratuito da Cloudflare; confirmar antes do plano de implementação.
