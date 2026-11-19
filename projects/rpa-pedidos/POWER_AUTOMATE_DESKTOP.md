# Laboratório: reproduzir o robô no Power Automate Desktop

Status: roteiro de implementação. Ainda não há fluxo nativo exportado ou execução validada no PAD.

## Preparação

Use Windows compatível com o [Power Automate Desktop](https://learn.microsoft.com/en-us/power-automate/desktop-flows/requirements), Python, Chrome ou Edge e o modo de automação web configurado no PAD. Este laboratório é assistido: você inicia o fluxo manualmente. Execução não assistida e disparo pela nuvem têm outros requisitos e licenciamento.

Copie este projeto para o Windows. Abra um terminal na pasta e rode `python demo.py`. Confirme que o formulário abre em `http://127.0.0.1:8770`. Não deixe o robô JavaScript rodando ao mesmo tempo.

## Variáveis

| Nome | Exemplo | Uso |
| --- | --- | --- |
| PastaProjeto | Caminho local da pasta do projeto | Localizar CSV e resultados |
| UrlPortal | http://127.0.0.1:8770 | Portal fictício |
| Pedidos | DataTable lida do CSV | Entrada do lote |
| LinhaAtual | Registro da iteração | Preencher campos |
| Tentativa | Número, inicialmente 1 | Limitar falhas técnicas |
| Status | Texto retornado pelo portal | Classificar processamento |
| Resultados | DataTable com pedido, status, tentativas e mensagem | Relatório |

## Construir o fluxo

Os nomes das ações variam com o idioma da instalação. Selecione a ação equivalente no painel do PAD.

1. Crie `RPA_Pedidos_Portfolio`. Defina `PastaProjeto` e `UrlPortal` como variáveis de entrada ou configuração no início.
2. Leia `dados\pedidos.csv` com a ação **Read from CSV file**: UTF-8, delimitador `;`, primeira linha com nomes das colunas.
3. Crie uma DataTable `Resultados` com colunas `pedido`, `status`, `tentativas`, `mensagem`.
4. Inicie Edge/Chrome e navegue para `UrlPortal`.
5. Capture os elementos do formulário. Prefira seletores baseados em `input[name="pedido"]`, `input[name="fornecedor"]`, `input[name="email"]`, `input[name="valor"]` e `button[type="submit"]`, evitando coordenadas na tela.
6. Para cada registro em `Pedidos`, chame um subfluxo `ProcessarPedido`. Preencha os quatro campos com as colunas correspondentes.
7. Pressione o botão **Cadastrar pedido**. Aguarde o elemento `#resultado` e consulte seu atributo `data-status` até sair de `aguardando`/`processando`, com limite total de 10 segundos. Não use apenas a existência do elemento: ele já existe antes do envio.
8. Se `cadastrado`, registre sucesso. Se `ja_existente`, registre como existente. Se `rejeitado`, leia o texto de `#resultado`, registre a rejeição e continue para a próxima linha.
9. Se `erro_tecnico` ou houver timeout/exceção, faça até três tentativas totais, recarregando o portal antes de preencher novamente. Depois do limite, registre erro técnico e continue. Não repita rejeições de negócio.
10. Capture a tela após cada resultado com o número da linha no nome. Acrescente uma linha a `Resultados` e grave o relatório CSV após cada pedido.
11. Ao terminar, feche o navegador. Preserve `output\pedidos.sqlite3` para testar a reexecução sem duplicatas.

Use tratamento de erro por bloco/subfluxo para que uma linha não interrompa todas as outras. [Referência Microsoft](https://learn.microsoft.com/en-us/power-automate/desktop-flows/errors).

## Critérios para considerar concluído

- Em base vazia: 3 cadastros, 1 já existente, 3 rejeições e nenhum erro técnico.
- Segunda execução: zero cadastros novos, 4 já existentes e 3 rejeições.
- Pedido conflitante preserva o valor anterior.
- Encerrar temporariamente o portal produz erro técnico registrado, sem sucesso falso.
- Capturas e CSV permitem identificar a linha e o motivo da rejeição.

Depois dos testes, inclua no repositório a exportação nativa feita pelo seu ambiente, a versão do PAD, os elementos necessários à configuração, os resultados observados e um vídeo curto com dados fictícios. Até lá, apresente este arquivo como roteiro de laboratório.

## Evolução intermediária nativa — ainda pendente

A versão 2 em Node/Python possui fila persistente, histórico e relatórios por execução. Para reproduzir isso no PAD, acrescente persistência de estado por item, identificador de lote, pasta por execução, separação entre erro técnico e de negócio e retomada apenas dos pendentes. Teste resposta perdida após gravação no destino. Esta extensão não está implementada como fluxo PAD neste pacote.

Se escolher as Work queues nativas da Power Platform, confira os requisitos de licença Premium e permissões em https://learn.microsoft.com/en-us/power-automate/desktop-flows/work-queues. Elas são diferentes da DataTable de entrada do roteiro.
