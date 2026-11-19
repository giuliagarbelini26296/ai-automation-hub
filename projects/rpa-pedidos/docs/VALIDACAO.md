# Validação local — versão 2 intermediária

Executada em 16/11/2026 no macOS, com Chrome instalado e Playwright 1.62.1.

- Quatro testes Python passaram: valores e precisão, identificador/e-mail, prevenção de duplicatas e conflito sem sobrescrita.
- Cinco testes Node passaram: exclusão mútua por trava, recuperação de fila e identificação do lote, checkpoint corrompido preservado, CSV com aspas/delimitadores/fórmulas e escaping HTML.
- Testes em navegador passaram: pausa após duas linhas, retomada das cinco restantes, repetição de lote concluído sem reenviar, histórico anterior preservado e capturas localizadas.
- Rejeições de negócio tiveram uma tentativa e foram mantidas para revisão.
- Ao perder a resposta após salvar, a segunda tentativa recebeu já existente; uma consulta ao SQLite confirmou um único pedido. O trace foi gerado.
- Uma indisponibilidade HTTP 503 chegou ao limite de três tentativas, com classificação de erro técnico. Nova execução sem a falha concluiu o pedido e preservou quatro tentativas totais.

A pasta exemplo contém execuções e entradas fictícias para explorar o relatório estático. A rotina do GitHub Actions ainda não foi executada no GitHub. Não foram validados Chromium neste computador, fluxo nativo PAD, ERP real ou operação em produção. Não foram medidas horas economizadas.
