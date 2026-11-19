'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const TERMINAIS=new Set(['cadastrado','ja_existente','rejeitado']);

function salvarAtomico(file,data){
 fs.mkdirSync(path.dirname(file),{recursive:true});
 const temp=file+'.'+crypto.randomUUID()+'.tmp';
 try{
  const fd=fs.openSync(temp,'wx');
  try{fs.writeFileSync(fd,JSON.stringify(data,null,2));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  fs.renameSync(temp,file);
 }finally{if(fs.existsSync(temp))fs.unlinkSync(temp);}
}

function bloquear(output){
 const file=path.join(output,'.robo.lock'),token=crypto.randomUUID();
 let fd;
 try{fd=fs.openSync(file,'wx');}
 catch(error){if(error.code==='EEXIST')throw Error('Já existe uma execução ou uma trava anterior nesta pasta. Confira .robo.lock; não remova enquanto o robô estiver ativo.');throw error;}
 try{fs.writeFileSync(fd,JSON.stringify({pid:process.pid,token,iniciada_em:new Date().toISOString()}));}finally{fs.closeSync(fd);}
 return ()=>{if(fs.existsSync(file)&&JSON.parse(fs.readFileSync(file,'utf8')).token===token)fs.unlinkSync(file);};
}

function abrirFila(rows,output){
 const hash=crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex');
 const file=path.join(output,'filas',hash.slice(0,24)+'.json');
 let fila;
 if(fs.existsSync(file)){
  fila=JSON.parse(fs.readFileSync(file,'utf8'));
  if(fila.schema!==1||fila.hash!==hash||!Array.isArray(fila.itens)||fila.itens.length!==rows.length)throw Error('Checkpoint incompatível. Preserve o arquivo e confira a pasta de saída.');
  fila.itens.forEach((item,i)=>{
   if(item.linha!==i+2 || JSON.stringify(item.dados)!==JSON.stringify(rows[i]) || !['pendente','processando','erro_tecnico',...TERMINAIS].includes(item.status) || !Number.isInteger(item.tentativas)||item.tentativas<0)throw Error('Checkpoint inválido; arquivo não será sobrescrito.');
  });
 }else fila={schema:1,hash,lote:hash.slice(0,24),criada_em:new Date().toISOString(),itens:rows.map((dados,i)=>({linha:i+2,dados,status:'pendente',tentativas:0}))};
 let recuperados=0;
 for(const item of fila.itens)if(item.status==='processando'){item.status='pendente';recuperados++;}
 salvarAtomico(file,fila);
 return {fila,file,recuperados};
}

module.exports={TERMINAIS,salvarAtomico,bloquear,abrirFila};
