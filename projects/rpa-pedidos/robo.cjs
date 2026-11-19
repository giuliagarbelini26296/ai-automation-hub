'use strict';
const {chromium}=require('playwright');
const {spawn,spawnSync}=require('node:child_process');
const {once}=require('node:events');
const fs=require('node:fs'),path=require('node:path'),readline=require('node:readline'),crypto=require('node:crypto');
const {TERMINAIS,salvarAtomico,bloquear,abrirFila}=require('./fila.cjs');
const {gerar}=require('./relatorios.cjs');

async function executar({input=path.join(__dirname,'dados/pedidos.csv'),output=path.join(__dirname,'output'),channel=process.env.RPA_BROWSER_CHANNEL,headed=false,maxItems=Infinity,simulateLostResponse=false,simulateUnavailable=false,trace=false}={}){
 if(maxItems!==Infinity&&(!Number.isInteger(maxItems)||maxItems<1))throw Error('O limite deve ser um inteiro positivo.');
 output=path.resolve(output);input=path.resolve(input);fs.mkdirSync(output,{recursive:true});
 const python=process.env.PYTHON || (process.platform==='win32'?'python':'python3');
 const csv=spawnSync(python,[path.join(__dirname,'ler_csv.py'),input],{encoding:'utf8'});
 if(csv.error || csv.status!==0)throw Error(csv.error?.message||csv.stderr||'Falha ao ler CSV.');
 const rows=JSON.parse(csv.stdout),liberar=bloquear(output);
 let server,browser,context,runDir,fila,file,summary,fatal;
 let processed=0,stopRequested=false,ignored=0,recovered=0;
 const started=Date.now(),runId=new Date().toISOString().replace(/[:.]/g,'-')+'-'+crypto.randomUUID().slice(0,8);
 const stop=()=>{stopRequested=true;};
 const persist=()=>{fila.atualizada_em=new Date().toISOString();salvarAtomico(file,fila);};
 const event=(tipo,extra={})=>fs.appendFileSync(path.join(runDir,'eventos.jsonl'),JSON.stringify({em:new Date().toISOString(),execucao:runId,lote:fila.lote,tipo,...extra})+'\n');
 process.on('SIGINT',stop);process.on('SIGTERM',stop);
 try{
  const opened=abrirFila(rows,output);({fila,file}=opened);recovered=opened.recuperados;
  ignored=fila.itens.filter(i=>TERMINAIS.has(i.status)).length;
  runDir=path.join(output,'execucoes',runId);fs.mkdirSync(path.join(runDir,'evidencias'),{recursive:true});
  event('inicio',{recuperados:recovered,ignorados:ignored});
  const pending=fila.itens.filter(i=>!TERMINAIS.has(i.status));
  if(pending.length){
   server=spawn(python,[path.join(__dirname,'demo.py'),'--port','0','--db',path.join(output,'pedidos.sqlite3'),...(simulateLostResponse?['--simulate-lost-response']:[]),...(simulateUnavailable?['--simulate-unavailable']:[])],{stdio:['ignore','pipe','pipe']});
   const url=await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('Portal não iniciou em 10 segundos.')),10000);
    const lines=readline.createInterface({input:server.stdout});
    lines.once('line',line=>{clearTimeout(timer);try{resolve(JSON.parse(line).url);}catch(e){reject(e);}lines.close();});
    server.once('error',error=>{clearTimeout(timer);reject(error);});
    server.once('exit',code=>{clearTimeout(timer);reject(Error('Portal encerrado: '+code));});
   });
   browser=await chromium.launch({headless:!headed,...(channel?{channel}:{})});
   context=await browser.newContext({viewport:{width:1100,height:1000}});
   if(trace)await context.tracing.start({screenshots:true,snapshots:true,sources:true});
   const page=await context.newPage();page.setDefaultTimeout(5000);
   for(const item of pending){
    if(stopRequested||processed>=maxItems)break;
    for(let tentativa=1;tentativa<=3;tentativa++){
     item.status='processando';item.tentativas++;item.execucao=runId;persist();
     event('tentativa',{linha:item.linha,pedido:item.dados.pedido,tentativa_total:item.tentativas});
     try{
      await page.goto(url,{waitUntil:'domcontentloaded'});
      for(const [field,label] of Object.entries({pedido:'Pedido',fornecedor:'Fornecedor',email:'E-mail',valor:'Valor em reais'}))await page.getByLabel(label,{exact:true}).fill(item.dados[field]);
      // Apenas a interface cadastra o pedido; o robô não chama a API diretamente.
      await page.getByRole('button',{name:'Cadastrar pedido',exact:true}).click();
      await page.waitForFunction(()=>['cadastrado','ja_existente','rejeitado','erro_tecnico'].includes(document.querySelector('#resultado').dataset.status));
      const status=await page.locator('#resultado').getAttribute('data-status');
      if(status==='erro_tecnico')throw Error('Falha de conexão no formulário.');
      const evidence=path.join(runDir,'evidencias',String(item.linha).padStart(4,'0')+'.png');
      await page.screenshot({path:evidence,fullPage:true});
      const resposta=JSON.parse(await page.locator('#resultado').innerText());
      const mensagem=resposta.erro || (status==='ja_existente'?'Pedido já cadastrado com os mesmos dados.':'Pedido cadastrado.');
      Object.assign(item,{status,mensagem,resposta_original:resposta,evidencia:path.relative(output,evidence).split(path.sep).join('/'),concluida_em:new Date().toISOString()});
      break;
     }catch(error){
      item.status='erro_tecnico';item.mensagem=error.message;
      event('falha_tecnica',{linha:item.linha,tentativa_total:item.tentativas,mensagem:error.message});
      if(tentativa<3&&!stopRequested)await new Promise(r=>setTimeout(r,500*2**(tentativa-1)));
      else break;
     }finally{persist();}
    }
    processed++;event('item_concluido',{linha:item.linha,status:item.status});
   }
  }
 }catch(error){fatal=error;}
 finally{
  try{
   if(context&&trace)await context.tracing.stop({path:path.join(runDir,'trace.zip')}).catch(e=>{fatal=fatal||e;});
   if(browser)await browser.close().catch(e=>{fatal=fatal||e;});
   if(server?.pid&&server.exitCode===null&&server.signalCode===null){const done=once(server,'exit');server.kill();await done;}
   if(runDir){
    const count=status=>fila.itens.filter(i=>i.status===status).length;
    const pending=fila.itens.filter(i=>!TERMINAIS.has(i.status)).length;
    summary={execucao:runId,lote:fila.lote,situacao:fatal?'falhou':count('erro_tecnico')?'requer_reprocessamento':pending?'pausada':'concluida',linhas:fila.itens.length,processados_agora:processed,ignorados_concluidos:ignored,recuperados:recovered,pendentes:pending,cadastrados:count('cadastrado'),ja_existentes:count('ja_existente'),rejeitados:count('rejeitado'),erros_tecnicos:count('erro_tecnico'),duracao_segundos:Number(((Date.now()-started)/1000).toFixed(2)),...(fatal?{erro:fatal.message}:{})};
    salvarAtomico(path.join(runDir,'itens.json'),fila.itens);
    salvarAtomico(path.join(runDir,'resumo.json'),summary);
    gerar(output,runDir,summary,fila.itens);
    event('fim',{situacao:summary.situacao});
   }
  }finally{process.removeListener('SIGINT',stop);process.removeListener('SIGTERM',stop);liberar();}
 }
 if(fatal)throw fatal;
 return {summary,results:fila.itens.map(i=>({...i,pedido:i.dados.pedido})),runDir};
}

function argumentos(args){
 const options={};
 for(let i=0;i<args.length;i++){
  const arg=args[i];
  if(arg==='--visivel')options.headed=true;
  else if(arg==='--trace')options.trace=true;
  else if(arg==='--simular-resposta-perdida')options.simulateLostResponse=true;
  else if(arg==='--simular-indisponibilidade')options.simulateUnavailable=true;
  else if(['--entrada','--saida','--limite'].includes(arg)){
   const value=args[++i];if(!value||value.startsWith('--'))throw Error('Informe um valor para '+arg);
   options[{'--entrada':'input','--saida':'output','--limite':'maxItems'}[arg]]=arg==='--limite'?Number(value):value;
  }else throw Error('Opção desconhecida: '+arg);
 }
 return options;
}
module.exports={executar,argumentos};
if(require.main===module){
 Promise.resolve().then(()=>executar(argumentos(process.argv.slice(2)))).then(({summary,runDir})=>{
  console.log(JSON.stringify(summary,null,2));console.log('Relatório: '+path.join(runDir,'relatorio.html'));
  if(summary.erros_tecnicos)process.exitCode=1;
 }).catch(e=>{console.error(e.message);process.exitCode=1;});
}
