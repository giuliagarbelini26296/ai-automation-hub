# Aprovação de documentos com Power Automate e SharePoint

> **Design kit — não validado.** Documentação e casos de teste apenas; nenhum fluxo foi executado em uma conta Microsoft.

**Status: kit de implementação.** Contém especificação, dados fictícios, sequência de ações e casos de teste. O fluxo ainda precisa ser criado ou importado, configurado e executado na sua conta Microsoft. Não há um pacote nativo validado neste repositório.

## Problema

Documentos enviados para revisão podem ficar sem responsável, decisão ou comentário registrado. O projeto propõe um processo de aprovação humana em uma biblioteca SharePoint, com status, responsável, prazo e tratamento de falhas.

Competências trabalhadas: Power Automate cloud, SharePoint, Approvals, expressões, condições, tratamento de erro e rastreabilidade de processos. É automação de workflow; a automação por interface fica no projeto RPA/PAD complementar.

## Duas maneiras de começar

1. **Construir o fluxo:** siga [IMPLEMENTAR.md](IMPLEMENTAR.md) para montar uma versão de estudo com uma biblioteca própria e campos em português.
2. **Adaptar uma base do GitHub:** faça fork de [PnP Power Automate Samples](https://github.com/pnp/powerautomate-samples) e use o exemplo [Request Review and Approval for a Selected File](https://github.com/pnp/powerautomate-samples/tree/main/samples/request-review-and-approval-for-a-selected-file), de Lindsay Shelton. Ele possui pacote de importação e instruções próprias. Preserve a licença MIT e os créditos. A coleção está arquivada e o exemplo deve ser revalidado no ambiente atual.

As colunas e o desenho do exemplo PnP diferem do nosso roteiro. Escolha uma abordagem. Importar o exemplo não dispensa configurar suas conexões, colunas e regras; não basta enviar o ZIP do original como se fosse uma implementação sua.

## Requisitos

- Acesso a um ambiente Power Automate com permissão para criar fluxos.
- SharePoint Online e uma biblioteca de documentos de estudo.
- Conexões e permissões para SharePoint e Approvals no ambiente escolhido.
- Uma conta de teste para aprovar/rejeitar. Se adicionar e-mail, conexão Outlook apropriada.

O fluxo cloud pode ser editado pelo navegador no Mac. Não precisa de Power Automate Desktop. A disponibilidade e o licenciamento dependem da sua conta e das políticas do ambiente. Consulte [o tutorial da Microsoft](https://learn.microsoft.com/en-us/power-automate/modern-approvals).

## Entregáveis previstos

| Arquivo/material | Situação |
| --- | --- |
| Especificação, ações e regras de erro | Incluídas neste kit |
| Casos de teste com entradas fictícias | Incluídos |
| Pacote exportado da implementação no seu ambiente | Pendente |
| Capturas de aprovação, rejeição e erro | Pendentes |
| Registro das adaptações e resultados medidos | Pendente |

## Evoluções que tornam a adaptação sua

- Bloquear nova solicitação para um documento já em aprovação.
- Roteamento por área, com aprovador de teste configurado por variável.
- Tempo limite e status para solicitações expiradas.
- Histórico em uma lista separada, com ID de execução e decisão.
- Relatório de quantidades por status, sem inventar ganhos de produtividade.

Implemente e teste uma melhoria por vez. Registre o comportamento anterior, o novo comportamento e evidências em `docs/ALTERACOES.md`.

## Publicar

Enquanto estiver nesta etapa, use uma descrição como: “Kit de estudo para implementar aprovação de documentos no Power Automate com SharePoint, incluindo regras, tratamento de falhas e plano de testes.” Após executar, atualize o status e documente o que você efetivamente concluiu.

Se exportar um fluxo, use o recurso nativo do Power Automate adequado ao seu ambiente: pacote para fluxo fora de solução ou exportação de solução quando exigida. [Documentação de importação e exportação](https://learn.microsoft.com/en-us/power-automate/export-import-flow-non-solution). Revise nomes do ambiente, IDs, e-mails e parâmetros antes de tornar o pacote público. Configure conexões novamente no destino.

## Créditos

Este kit de documentação foi preparado para Giulia Garbelini com apoio de IA. Nenhum pacote PnP foi copiado para esta pasta. A referência de terceiros e sua autoria estão descritas em [REFERENCIAS.md](REFERENCIAS.md). Licença MIT para o conteúdo original deste kit; materiais adaptados continuam com suas licenças e créditos.
