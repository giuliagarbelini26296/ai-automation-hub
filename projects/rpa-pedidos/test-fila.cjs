const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {abrirFila,bloquear,salvarAtomico}=require('./fila.cjs');
const {csv,gerar}=require('./relatorios.cjs');
const row={pedido:'PED-0001',fornecedor:'Empresa <fictícia>',email:'a@exemplo.example',valor:'10,00'};
function temp(fn){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'fila-rpa-'));try{return fn(dir);}finally{fs.rmSync(dir,{recursive:true,force:true});}}

test('trava impede duas execuções na mesma pasta e libera para a próxima',()=>temp(dir=>{
 const release=bloquear(dir);assert.throws(()=>bloquear(dir),/trava anterior/);release();bloquear(dir)();
}));
test('recupera item em processamento, preserva concluídos e identifica novo conteúdo',()=>temp(dir=>{
 const opened=abrirFila([row,{...row,pedido:'PED-0002'}],dir);
 opened.fila.itens[0].status='cadastrado';opened.fila.itens[1].status='processando';opened.fila.itens[1].tentativas=1;
 salvarAtomico(opened.file,opened.fila);const resumed=abrirFila([row,{...row,pedido:'PED-0002'}],dir);
 assert.equal(resumed.recuperados,1);assert.equal(resumed.fila.itens[0].status,'cadastrado');assert.equal(resumed.fila.itens[1].status,'pendente');assert.equal(resumed.fila.itens[1].tentativas,1);
 assert.notEqual(abrirFila([{...row,valor:'20'}],dir).fila.lote,resumed.fila.lote);
}));
test('checkpoint corrompido não é silenciosamente apagado',()=>temp(dir=>{
 const opened=abrirFila([row],dir);fs.writeFileSync(opened.file,'{arquivo interrompido');
 assert.throws(()=>abrirFila([row],dir));assert.equal(fs.readFileSync(opened.file,'utf8'),'{arquivo interrompido');
}));
test('CSV escapa delimitadores, aspas e fórmulas',()=>{
 const text=csv([['=1+1','a;b','a"b','10,00']]);assert.ok(text.includes('"\'=1+1"'));assert.ok(text.includes('"a;b"'));assert.ok(text.includes('"a""b"'));
});
test('relatório mantém texto de entrada como texto e aponta para evidências',()=>temp(dir=>{
 const runDir=path.join(dir,'execucoes','teste');fs.mkdirSync(runDir,{recursive:true});
 const summary={execucao:'teste',lote:'a',situacao:'concluida',linhas:1,processados_agora:1,pendentes:0,rejeitados:1,erros_tecnicos:0,ignorados_concluidos:0,duracao_segundos:1};salvarAtomico(path.join(runDir,'resumo.json'),summary);
 gerar(dir,runDir,summary,[{dados:row,linha:2,status:'rejeitado',tentativas:1,mensagem:'<script>alert(1)</script>',evidencia:'execucoes/teste/evidencias/0002.png'}]);
 const html=fs.readFileSync(path.join(runDir,'relatorio.html'),'utf8');assert.ok(!html.includes('<script>'));assert.ok(html.includes('&lt;script&gt;'));assert.ok(html.includes('../../execucoes/teste/evidencias/0002.png'));assert.ok(fs.existsSync(path.join(dir,'historico.csv')));
}));
