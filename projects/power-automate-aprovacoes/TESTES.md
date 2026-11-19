# Plano de testes — ainda não executado no Power Automate

| Caso | Preparação | Ação | Resultado esperado |
| --- | --- | --- | --- |
| Aprovar | Arquivo Novo, aprovador de teste válido | Iniciar e aprovar com comentário | Aprovado, comentário, data e execução registrados |
| Rejeitar | Outro arquivo Novo | Rejeitar com comentário | Rejeitado, motivo e data registrados |
| Comentário vazio | Arquivo Novo | Aprovar sem comentário | Aprovado sem falha de expressão |
| Falta de aprovador | Arquivo sem Aprovador | Iniciar | Erro; nenhuma aprovação criada |
| Reenvio simultâneo | Arquivo Em aprovacao | Disparar de novo | Nenhuma segunda aprovação ao processar a segunda execução |
| Arquivo já decidido | Arquivo Aprovado/Rejeitado | Iniciar | Fluxo encerra sem nova aprovação |
| Expiração | Novo, timeout de teste curto | Não responder até expirar | Expirado ou erro de configuração explicitamente identificado; nunca sucesso falso |
| Falha de permissão | Retirar acesso da conexão em ambiente de teste | Executar | Execução falha; trilha identifica ação e erro |
| Reprocessamento | Corrigir erro e deixar status Erro | Iniciar | Nova execução rastreável, sem sobrescrever histórico externo se houver |

Quando executados, acrescente uma coluna “Obtido”, data e caminho da evidência. Use apenas contas e bibliotecas destinadas a testes. Não retire permissões de um ambiente de trabalho para cumprir este roteiro.
