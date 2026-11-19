# Fluxo n8n: webhook-llm-triage

Arquivo: [`webhook-llm-triage.json`](webhook-llm-triage.json) (importe em n8n via *Workflows → Import from File*).

> **Status honesto:** este fluxo foi escrito à mão como JSON e validado **apenas estruturalmente** pelo teste `tests/test_rules_and_n8n.py::test_n8n_workflow_structure` (tipos de nó, conexões, URL, cabeçalho de assinatura, ausência de segredo literal). Ele **não foi importado nem executado** em uma instância n8n. Versões de nó (`typeVersion`) podem precisar de ajuste na sua versão do n8n.

## O que o fluxo faz

```text
Webhook (POST /webhook/pedidos-triage)
  → Assinar HMAC (Crypto, SHA256, segredo de $env.WEBHOOK_SECRET)
  → Enviar para Triage API (HTTP Request, POST {TRIAGE_API_URL}/webhooks/pedidos, cabeçalho X-Signature-256)
  → Aceito? (IF: statusCode < 300)
      ├─ true  → Resultado aceito   (Set: resultado = enfileirado | duplicado_ignorado, queue_id, status_url)
      └─ false → Resultado rejeitado (Set: resultado = rejeitado, http_status, erro)
```

- O corpo assinado e o corpo enviado usam a mesma expressão `JSON.stringify($json.body)`, para que a assinatura HMAC confira na API.
- `responseMode: lastNode`: quem chamou o webhook do n8n recebe o resultado do último nó (`Set`).
- O HTTP Request usa `neverError` + `fullResponse`, para que respostas 4xx da API sigam pelo ramo `false` em vez de interromper o fluxo.

## Configuração necessária (não testada)

- Variáveis de ambiente na instância n8n: `WEBHOOK_SECRET` (o mesmo da API) e `TRIAGE_API_URL` (ex.: `http://host.docker.internal:8102` se n8n roda em Docker e a API no host).
- O acesso a `$env` em expressões pode estar bloqueado por `N8N_BLOCK_ENV_ACCESS_IN_NODE`; nesse caso, use credenciais do n8n no lugar.
- O webhook do próprio n8n está sem autenticação neste exemplo. Em uso real, configure *Header Auth* no nó Webhook.

Apenas n8n foi considerado; não há suporte a Make neste projeto.
