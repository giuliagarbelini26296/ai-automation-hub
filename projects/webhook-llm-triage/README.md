# webhook-llm-triage

> **Extensão criada em nov/2026 com apoio de IA (Claude Code).** Não existia no portfólio original. Dados fictícios; não é produção.

API em Python 3.12 + FastAPI que recebe eventos de pedidos e mensagens de suporte de um e-commerce fictício, valida assinatura e conteúdo, enfileira em SQLite e faz triagem com um passo de LLM cuja saída é validada por schema.

## Fluxo

1. `POST /webhooks/pedidos` com JSON e cabeçalho `X-Signature-256: sha256=<hmac do corpo bruto>` (segredo em `WEBHOOK_SECRET`).
2. Verificação HMAC-SHA256 (`hmac.compare_digest`) → 401 se inválida.
3. Validação Pydantic (`extra="forbid"`, formatos de pedido/e-mail/valor) → 400 (JSON malformado), 413 (corpo grande), 415 (Content-Type), 422 (campos), com lista `details[].field`.
4. Idempotência: chave = cabeçalho `Idempotency-Key` ou `event_id`. Repetição com mesmo conteúdo → 200 `duplicate: true`; mesma chave com outro conteúdo → 409.
5. Fila persistente SQLite (`queued → processing → done | dead_letter`). Itens `processing` voltam para a fila ao reiniciar.
6. Worker (thread no mesmo processo) chama o provedor de LLM:
   - `LLM_PROVIDER=fake` (padrão): regras determinísticas (`RuleBasedLLM`), sem rede.
   - `LLM_PROVIDER=openai`: qualquer API compatível com `/chat/completions` (OpenAI, ou Ollama com `LLM_BASE_URL=http://localhost:11434/v1`), com `response_format` JSON Schema `strict`.
   - Saída sempre validada pelo modelo Pydantic `Triage` (`category`, `priority`, `summary`, `suggested_action`). Se vier fora do schema → fallback para regras (`fallback_used: true`).
   - 429/5xx/timeout → retry com backoff exponencial + jitter (`BACKOFF_BASE_S`, `BACKOFF_MAX_S`); após `MAX_ATTEMPTS` → `dead_letter`.
7. Hand-off opcional para o `rpa-pedidos`: se `RPA_HANDOFF_DIR` estiver definido e a ação for `send_to_rpa`, grava `<event_id>.csv` no formato de entrada do robô (`pedido;fornecedor;email;valor`).
8. `GET /events/{id}`, `GET /stats` (contagens) e `GET /health`. Logs JSON no stdout.

O provedor OpenAI-compatível foi testado apenas com respostas simuladas (`httpx.MockTransport`); **nenhuma chamada real a OpenAI ou Ollama foi feita**.

## Executar (comandos verificados no macOS, Python 3.12)

```sh
cd projects/webhook-llm-triage
python3.12 -m venv .venv
.venv/bin/pip install --no-cache-dir -r requirements-dev.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m pytest

export WEBHOOK_SECRET=segredo-local-de-demonstracao-123   # exemplo; use o seu
.venv/bin/uvicorn --factory app.main:create_app --host 127.0.0.1 --port 8102
# em outro terminal, com o mesmo WEBHOOK_SECRET:
TRIAGE_API_URL=http://127.0.0.1:8102 .venv/bin/python scripts/send_event.py examples/pedido-novo.json
```

Docker: `Dockerfile` e `docker-compose.yml` estão incluídos, mas **não foram construídos/executados** nesta validação (pouco espaço em disco). O compose publica em `127.0.0.1:8102`.

## Exemplo real (execução local de 19/11/2026, provedor `fake-rules`)

```text
202 {"id": "evq_15f5916ba57841ab", "status": "queued", "duplicate": false, "status_url": "/events/evq_15f5916ba57841ab"}
200 {"id": "evq_15f5916ba57841ab", "status": "done", "duplicate": true, ...}           # mesmo evento reenviado
422 {"error": {"code": "validation_error", ... "field": "customer.email" ... "order.order_id" ... "order.amount" ...}}
401 {"error": {"code": "invalid_signature", "message": "Cabeçalho X-Signature-256 ausente ou inválido."}}
```

`GET /events/evq_15f5916ba57841ab` (trecho):

```json
"status": "done", "attempts": 1,
"triage": {"category": "new_order", "priority": "low",
           "summary": "Novo pedido PED-0101 de Fornecedor Horizonte Fictício, valor R$ 890.00.",
           "suggested_action": "send_to_rpa"},
"llm_provider": "fake-rules", "fallback_used": false
```

CSV de hand-off gerado e depois processado pelo robô com `node robo.cjs --entrada <arquivo>.csv --saida <pasta>` → `"situacao": "concluida", "cadastrados": 1, "rejeitados": 0`.

## Limitações

- Worker único no mesmo processo; sem fila distribuída nem múltiplas réplicas.
- `GET /events/{id}` e `/stats` não têm autenticação: use somente localmente.
- Sem proteção contra replay além da idempotência (não há timestamp assinado).
- Regras do `fake` são palavras-chave simples, não um modelo; não houve avaliação de qualidade de um LLM real.
- Reprocessamento manual de `dead_letter` ainda não existe (trabalho futuro).
