const {executar}=require('./robo.cjs');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
(async()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'rpa-intermediario-'));
 try{
  const output=path.join(root,'retomada');
  const paused=await executar({output,maxItems:2});
  assert.equal(paused.summary.situacao,'pausada');assert.equal(paused.summary.processados_agora,2);assert.equal(paused.summary.pendentes,5);
  const before=fs.readFileSync(path.join(paused.runDir,'resumo.json'),'utf8');
  const resumed=await executar({output});
  assert.equal(resumed.summary.linhas,7);assert.equal(resumed.summary.processados_agora,5);assert.equal(resumed.summary.ignorados_concluidos,2);
  assert.equal(resumed.summary.cadastrados,3);assert.equal(resumed.summary.ja_existentes,1);assert.equal(resumed.summary.rejeitados,3);assert.equal(resumed.summary.erros_tecnicos,0);
  assert.equal(fs.readFileSync(path.join(paused.runDir,'resumo.json'),'utf8'),before);
  assert.ok(resumed.results.filter(r=>r.status==='rejeitado').every(r=>r.tentativas===1));
  for(const r of resumed.results)assert.ok(fs.existsSync(path.join(output,r.evidencia)));
  const repeated=await executar({output});assert.equal(repeated.summary.processados_agora,0);assert.equal(repeated.summary.ignorados_concluidos,7);
  assert.equal(fs.readdirSync(path.join(output,'execucoes')).length,3);
  assert.ok(fs.readFileSync(path.join(resumed.runDir,'excecoes.csv'),'utf8').includes('PED-0004'));
  const input=path.join(root,'um-pedido.csv');fs.writeFileSync(input,'pedido;fornecedor;email;valor\nPED-0099;Empresa Fictícia;a@exemplo.example;10,01\n');
  const lostOutput=path.join(root,'resposta-perdida');
  const lost=await executar({input,output:lostOutput,simulateLostResponse:true,trace:true});
  assert.equal(lost.summary.erros_tecnicos,0);assert.equal(lost.results[0].status,'ja_existente');assert.equal(lost.results[0].tentativas,2);
  assert.ok(fs.existsSync(path.join(lost.runDir,'trace.zip')));
  const python=process.env.PYTHON||(process.platform==='win32'?'python':'python3');
  const count=spawnSync(python,['-c','import sqlite3,sys;print(sqlite3.connect(sys.argv[1]).execute("SELECT COUNT(*) FROM pedidos").fetchone()[0])',path.join(lostOutput,'pedidos.sqlite3')],{encoding:'utf8'});
  assert.equal(count.status,0);assert.equal(count.stdout.trim(),'1');
  const outageOutput=path.join(root,'indisponibilidade');
  const outage=await executar({input,output:outageOutput,simulateUnavailable:true});
  assert.equal(outage.summary.situacao,'requer_reprocessamento');assert.equal(outage.results[0].tentativas,3);assert.equal(outage.summary.erros_tecnicos,1);assert.equal(outage.summary.rejeitados,0);
  const recovery=await executar({input,output:outageOutput});
  assert.equal(recovery.summary.cadastrados,1);assert.equal(recovery.results[0].tentativas,4);assert.equal(recovery.summary.erros_tecnicos,0);
  console.log('RPA intermediário verificado: pausa/retomada, histórico preservado, rejeições sem retentativa, resposta perdida sem duplicata, trace, indisponibilidade e reprocessamento.');
 }finally{fs.rmSync(root,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
