# RPA intermediário — processamento de pedidos com recuperação e auditoria

Projeto de portfólio que simula um processo operacional completo: lê um lote CSV, cria uma fila persistente, cadastra pedidos pela interface de um sistema fictício e separa exceções para revisão humana. A versão 2 inclui retomada por item, histórico de execuções e cenários de falha verificáveis.

![Portal de demonstração com dados fictícios](docs/demonstracao.png)

> Nota da cópia no AI Automation Hub: a pasta `docs/exemplo/` (relatórios, eventos e screenshots de execuções) não foi incluída neste repositório. Gere um relatório próprio com `npm run demo`; ele fica em `output/execucoes/<id>/relatorio.html`.

![Relatório de processamento e exceções](docs/central-execucao.png)

## Escopo intermediário

| Recurso | Comportamento implementado |
| --- | --- |
| Fila persistente | Cada linha possui estado, número de tentativas e resultado |
| Identificação do lote | Hash dos registros de entrada; alteração dos dados gera outro lote |
| Retomada | Itens concluídos não são reenviados; pendentes e erros técnicos podem continuar |
| Separação de exceções | Rejeição de negócio termina a linha; falha técnica admite novas tentativas |
| Retentativa | Até três tentativas por item em cada execução, com intervalo progressivo |
| Prevenção de duplicatas | Chave única no destino e conferência dos dados de pedido existente |
| Auditoria | Pasta própria por execução, eventos com horário, screenshots e snapshot dos itens |
| Revisão humana | CSV de exceções com dados de entrada e motivo da rejeição |
| Acompanhamento | Relatório HTML por execução e histórico CSV para Excel ou Power BI |
| Proteção de execução | Trava local impede dois robôs escrevendo na mesma pasta ao mesmo tempo |
| Diagnóstico | Gravação opcional de trace do Playwright |
| Testes de falha | Resposta perdida após salvar e indisponibilidade HTTP 503 simuladas |

O nível “intermediário” descreve o escopo de estudo proposto; não é uma certificação de senioridade. O projeto não possui integração com ERP real, fila distribuída ou execução validada em produção.

## Tecnologias e responsabilidades

- **Python:** leitura do CSV, validação de pedidos e servidor de demonstração.
- **Node.js e Playwright:** preenchimento e envio pelo navegador.
- **SQLite:** persistência do sistema fictício de destino.
- **JSON:** fila local gravada por substituição atômica; sem múltiplos trabalhadores.
- **HTML/CSV:** evidências para revisar resultados e analisar execuções.

O robô não chama diretamente a API para cadastrar pedidos. Ele preenche campos e pressiona o botão do formulário. Não envia e-mails nem realiza pagamentos.

## Instalar e executar

Requisitos: Python 3.9+, Node.js 20+ e npm. Dentro desta pasta:

```sh
npm install
npx playwright install chromium
npm run demo -- --visivel
```

Sem `--visivel`, roda em segundo plano. Para usar Chrome instalado, configure `RPA_BROWSER_CHANNEL=chrome` no seu terminal. `PYTHON` pode indicar o executável Python; por padrão usa `python` no Windows e `python3` nos outros sistemas.

O robô inicia um portal local em uma porta disponível e o encerra no final. Para explorar apenas o formulário, rode `python3 demo.py` e abra `http://127.0.0.1:8770`; no Windows, use `python` quando necessário. Abrir `portal.html` como arquivo isolado não inicia o sistema e não permite cadastrar pedidos.

## Demonstração de pausa e retomada

Use uma pasta nova para observar todos os estados desde o início:

```sh
npm run demo -- --saida output/estudo-retomada --limite 2
npm run demo -- --saida output/estudo-retomada
npm run demo -- --saida output/estudo-retomada
```

1. A primeira execução processa duas linhas e termina como `pausada`, com cinco pendentes.
2. A segunda preserva as duas linhas concluídas e processa apenas as cinco restantes.
3. A terceira identifica as sete linhas concluídas e não abre navegador para reenviá-las.

Com `Ctrl+C` ou SIGTERM, o robô solicita parada após a tentativa atual e preserva a fila. Se o processo for encerrado de forma abrupta, itens que ficaram `processando` voltam a `pendente` ao carregar o checkpoint. Se o sistema de destino tiver salvo antes da interrupção, sua chave única evita outro cadastro.

Após encerramento forçado, uma trava `.robo.lock` pode permanecer. Confira o PID registrado e confirme que o robô não está mais ativo antes de remover **somente essa trava**. Não apague a fila ou o banco para “retomar”. O projeto não remove travas antigas automaticamente.

## Demonstrar resposta perdida sem duplicação

```sh
npm run demo -- --saida output/estudo-resposta --simular-resposta-perdida --trace
```

Na primeira submissão, o servidor salva o pedido e fecha a conexão antes da resposta. O robô registra falha técnica, tenta novamente e recebe `ja_existente`. O teste automatizado confere que existe um único pedido no banco para essa entrada.

O trace é salvo na pasta da execução. Abra com:

```sh
npx playwright show-trace CAMINHO_DO_TRACE_ZIP
```

## Demonstrar indisponibilidade e recuperação

```sh
npm run demo -- --saida output/estudo-falha --limite 1 --simular-indisponibilidade
npm run demo -- --saida output/estudo-falha
```

A primeira execução recebe HTTP 503, tenta até três vezes e registra `erro_tecnico`. O comando retorna código de erro. Na segunda, o portal volta ao normal e a linha é processada novamente. A tentativa anterior continua registrada no histórico e no contador total do item.

As opções de simulação afetam somente o sistema fictício iniciado pelo próprio robô.

## Entrada e regras

A entrada padrão é `dados/pedidos.csv`, em UTF-8, delimitada por `;`, com cabeçalho `pedido;fornecedor;email;valor`. Outra entrada pode ser definida por `--entrada CAMINHO`.

Valores usam vírgula ou ponto decimal, sem separador de milhar. São convertidos a centavos no destino. Pedido tem formato `PED-0001`; fornecedor e e-mail são obrigatórios; valor deve ser positivo, até R$ 1 milhão e ter até duas casas decimais.

O lote padrão tem sete linhas: três pedidos válidos inéditos, uma repetição idêntica e três rejeições (e-mail inválido, valor negativo e conflito de valor). Em base vazia, o fechamento do lote tem **3 cadastrados, 1 já existente e 3 rejeitados**.

Um cadastro conflitante não sobrescreve o pedido original. Rejeições não são repetidas automaticamente. Para corrigir uma rejeição, revise a causa, altere a entrada CSV e execute: a alteração cria outro lote. Os pedidos já salvos seguem protegidos pela validação no destino.

## Arquivos gerados

```text
output/
  pedidos.sqlite3
  .robo.lock                    # existe somente durante execução normal
  filas/<hash-do-lote>.json     # checkpoint atualizado após cada tentativa
  historico.csv                # uma linha por execução
  execucoes/<id>/
    resumo.json
    itens.json                 # snapshot do lote ao fim desta execução
    eventos.jsonl
    excecoes.csv
    relatorio.html
    trace.zip                  # somente com --trace
    evidencias/*.png
```

Os relatórios anteriores são preservados. O histórico é reconstruído dos resumos existentes. O banco do destino é compartilhado entre lotes da mesma pasta de saída, para que a mesma compra não seja inserida de novo em outra entrada.

As contagens `cadastrados`, `ja_existentes` e `rejeitados` descrevem o estado acumulado do lote. `processados_agora` mostra quantas linhas foram tentadas nesta execução. O contador de pendentes inclui erros técnicos que ainda podem ser reprocessados. Uma repetição de lote concluído terá `processados_agora = 0`, preservando os resultados anteriores.

Preserve toda a pasta de saída para manter as referências às evidências. O histórico CSV pode ser importado no Excel/Power BI; um painel Power BI não foi incluído. O relatório HTML é estático e pode ser aberto localmente.

## Verificação

```sh
npm test
npm run test:e2e
```

Os testes cobrem regras de validação, precisão monetária, duplicatas, conflitos, trava de execução, checkpoint corrompido, recuperação de item em processamento, escaping de relatórios e fórmulas no CSV. No navegador, cobrem pausa/retomada, histórico preservado, rejeições sem retentativa, resposta perdida após salvar, ausência de duplicata, trace e reprocessamento após indisponibilidade.

Veja [a validação local](docs/VALIDACAO.md). Os testes foram executados com Chrome no macOS. O workflow do GitHub Actions deste hub fica em `.github/workflows/ci.yml` na raiz do repositório, mas sua execução no GitHub e a instalação do Chromium no computador de quem clonar devem ser confirmadas depois de publicar.

## Power Automate Desktop

[O laboratório PAD](POWER_AUTOMATE_DESKTOP.md) descreve a reprodução do cadastro em Windows. A fila persistente, auditoria e relatórios desta versão estão implementados em Node/Python; sua reprodução nativa no PAD está descrita como evolução pendente, sem exportação validada.

## Próximas melhorias

- Aprovação humana de pedidos acima de um limite antes do envio.
- Integração com um ERP de testes com autenticação e credenciais fora do código.
- Fila gerenciada e múltiplos trabalhadores, com controle de concorrência no destino.
- Painel Power BI a partir do histórico real de execuções.

## Autoria e referências

Implementação original preparada para o portfólio de Giulia Garbelini com apoio de IA. Estude, execute e personalize antes de apresentar em entrevistas. Empresas e dados são fictícios; nenhum código foi copiado de um projeto de terceiros.

- [Playwright: biblioteca](https://playwright.dev/docs/library)
- [Playwright: seletores por rótulo e função](https://playwright.dev/docs/locators)
- [Playwright: diagnóstico com trace](https://playwright.dev/docs/trace-viewer)
- [Microsoft: requisitos do PAD](https://learn.microsoft.com/en-us/power-automate/desktop-flows/requirements)

Licença MIT. Não há métricas de economia de tempo ou implantação em produção comprovadas.
