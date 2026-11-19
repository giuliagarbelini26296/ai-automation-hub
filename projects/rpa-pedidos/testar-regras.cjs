const {spawnSync}=require('node:child_process');
const python=process.env.PYTHON || (process.platform==='win32'?'python':'python3');
const result=spawnSync(python,['-m','unittest','-v','test_demo.py'],{cwd:__dirname,stdio:'inherit'});
if(result.error)console.error(result.error.message);
process.exitCode=result.status===null?1:result.status;
