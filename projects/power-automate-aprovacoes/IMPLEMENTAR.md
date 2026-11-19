# Construção do fluxo de estudo

Este documento é uma especificação para montar no editor do Power Automate. Não é JSON importável ou exportação nativa. Os rótulos das ações podem mudar conforme o idioma do editor.

## 1. Biblioteca e colunas

Crie uma biblioteca SharePoint `DocumentosPortfolio`. Para simplificar expressões, crie inicialmente as colunas com os nomes sem acentos abaixo; depois pode alterar apenas o nome exibido. Não use a biblioteca de produção de uma empresa.

| Coluna | Tipo | Configuração |
| --- | --- | --- |
| StatusRevisao | Escolha | Novo, Em aprovacao, Aprovado, Rejeitado, Expirado, Erro |
| Aprovador | Pessoa | Uma única pessoa, preenchimento obrigatório antes do envio |
| ComentarioRevisao | Múltiplas linhas de texto | Decisão ou motivo do erro |
| ExecucaoId | Uma linha de texto | Identificador da execução |
| DataDecisao | Data e hora | Preencher ao concluir |

Defina `Novo` como padrão de `StatusRevisao`. Coloque três documentos fictícios sem informações pessoais. O arquivo `dados/casos.csv` orienta os cenários; ele não cria automaticamente a biblioteca nem envia documentos.

## 2. Gatilho e controle do processo

1. Crie um fluxo instantâneo com SharePoint **For a selected file**. Selecione o site e a biblioteca de teste.
2. Nas configurações do gatilho, habilite o controle de concorrência e limite a uma execução para o laboratório. Como uma aprovação pode ficar aguardando, isso serializa todas as solicitações deste fluxo. É uma escolha didática, não um mecanismo adequado a alto volume.
3. Leia os metadados usando **Get file properties**, com o ID do arquivo selecionado.
4. Se o status for diferente de `Novo` ou `Erro`, encerre sem criar outra aprovação. Para reenviar um documento aprovado/rejeitado/expirado, o processo de teste exige voltar explicitamente a `Novo`.
5. Verifique se o campo Aprovador possui e-mail. Se estiver vazio, atualize para `Erro`, comente “Aprovador não configurado” e encerre como falha. Use o e-mail dinâmico da coluna Pessoa, nunca uma string de nome de pessoa como destinatário.

## 3. Bloco de processamento

Crie um **Scope** chamado `Processar` contendo:

1. **Update file properties:** `StatusRevisao = Em aprovacao`, `ExecucaoId = workflow()?['run']?['name']`. Preserve os campos obrigatórios da biblioteca.
2. **Start and wait for an approval:** tipo Approve/Reject – First to respond. Título com o nome do documento. Assigned to com o e-mail de Aprovador. Item link com o link dinâmico do arquivo. Configure timeout de teste `PT10M` nas configurações da ação; documente se seu ambiente usar outro limite.
3. Uma condição compara o campo dinâmico **Outcome** da aprovação a `Approve`. Use o valor técnico retornado, que não é a tradução do texto da interface.
4. No ramo positivo, atualize `StatusRevisao = Aprovado`. No negativo, `Rejeitado`. Defina `DataDecisao = utcNow()` em ambos. Para comentário, use o conteúdo de Comments de cada resposta retornada pela aprovação. Mesmo com um aprovador, as respostas podem vir como coleção: processe a coleção em **Apply to each** quando o editor assim exigir.

Um comentário ausente deve resultar em texto vazio, não em falha. A aprovação humana é a decisão do processo; não aprove automaticamente documentos em nome do usuário.

## 4. Falhas, expiração e fechamento

Crie um Scope `Falha` depois de `Processar`. Em **Configure run after**, selecione **has failed** e **has timed out** para `Processar`.

- Se a ação de aprovação estiver `TimedOut`, grave `Expirado` e o motivo “Prazo de resposta esgotado”. Uma expressão possível, com a ação renomeada exatamente para `Aguardar_aprovacao`, é `equals(actions('Aguardar_aprovacao')?['status'], 'TimedOut')`.
- Nos demais casos, grave `Erro`, uma mensagem resumida e o ID de execução. Não atualize para Aprovado quando uma ação falhar.
- Se o próprio SharePoint estiver indisponível, a atualização de status também pode falhar. O registro da execução no Power Automate será a evidência; configure Terminate com status Failed e documente a necessidade de correção/reexecução.
- Falhas ao notificar, caso você acrescente e-mail depois da decisão, não devem apagar uma decisão já registrada. Separe a notificação do Scope de decisão.

Acrescente um Scope `Finalizar` com execução após sucesso, falha, timeout ou skipped do Scope `Falha` para registrar o encerramento. Não use um Terminate Succeeded que esconda uma falha do processamento. [Orientações de tratamento de erros da Microsoft](https://learn.microsoft.com/en-us/power-automate/guidance/coding-guidelines/error-handling).

Timeout do fluxo não garante cancelamento da aprovação pendente. Se o ambiente mantiver uma aprovação aberta, cancele-a no ambiente de teste e registre o procedimento. Não apresente esse exemplo como solução de concorrência ou cancelamento em produção.

## 5. Testar e exportar

Execute todos os casos de `TESTES.md`. Salve capturas com dados fictícios. Registre versões, conexões necessárias e o resultado real em `docs/ALTERACOES.md`. Exporte o pacote pelo editor somente depois da validação e atualize o README com a situação correta.
