// Bootstrap a machine-local virtual environment; never commit .venv to Git.
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { spawn, spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
const root=dirname(dirname(fileURLToPath(import.meta.url))),backend=join(root,'backend')
const windows=process.platform==='win32'
const python=join(backend,'.venv',windows?'Scripts':'bin',windows?'python.exe':'python')
const task=process.argv[2]||'start',extra=process.argv.slice(3)
const env={...process.env,PYTHONUTF8:'1',PYTHONUNBUFFERED:'1',PIP_DISABLE_PIP_VERSION_CHECK:'1'}
function run(command,args,cwd=root){
  const result=spawnSync(command,args,{cwd,env,stdio:'inherit'})
  if(result.error||result.status!==0)throw new Error('Команда не выполнена. Проверьте сообщение выше.')
}
function systemPython(){
  const choices=windows?[['py',['-3.12']],['py',['-3']],['python',[]]]:[['python3.12',[]],['python3',[]],['python',[]]]
  for(const [command,args] of choices){
    const result=spawnSync(command,[...args,'-c','import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'],{env,stdio:'ignore'})
    if(!result.error&&result.status===0)return [command,args]
  }
  throw new Error('Установите Python 3.12+ (на Windows включите Add Python to PATH), затем повторите запуск.')
}
try{
  if(!existsSync(python)){
    console.log('Первый запуск: создаю backend/.venv для этого компьютера…')
    const [command,args]=systemPython()
    run(command,[...args,'-m','venv',join(backend,'.venv')])
  }
  const digest=createHash('sha256').update(readFileSync(join(backend,'requirements.lock'))).digest('hex')
  const marker=join(backend,'.venv','.tipro-requirements')
  if(!existsSync(marker)||readFileSync(marker,'utf8')!==digest){
    console.log('Устанавливаю зависимости Python…')
    run(python,['-m','pip','install','-r',join(backend,'requirements.lock')])
    writeFileSync(marker,digest)
  }
  if(!existsSync(join(backend,'.env')))run(python,[join(backend,'scripts','init_env.py'),'--port','55432'])
  if(task==='start'&&!existsSync(join(root,'node_modules','vite','bin','vite.js'))){
    console.log('Устанавливаю зависимости Vue…')
    if(windows)run(process.env.ComSpec||'cmd.exe',['/d','/s','/c','npm.cmd install'])
    else run('npm',['install'])
  }
  const commands={
    start:{args:[join(root,'scripts','start.py')],cwd:root},
    api:{args:['-m','uvicorn','app.main:app','--reload','--host','127.0.0.1','--port','8000','--no-access-log'],cwd:backend},
    test:{args:['-m','pytest','-q'],cwd:backend},
    schema:{args:[join(backend,'scripts','export_schema.py')],cwd:root},
    admin:{args:['-m','app.cli','create-admin'],cwd:backend},
  }
  const command=commands[task]
  if(!command)throw new Error('Неизвестная команда запуска.')
  const child=spawn(python,[...command.args,...extra],{cwd:command.cwd,env,stdio:'inherit'})
  process.on('SIGINT',()=>{if(!windows)child.kill('SIGINT')})
  process.on('SIGTERM',()=>child.kill('SIGTERM'))
  child.on('error',()=>{console.error('Не удалось запустить Python.');process.exitCode=1})
  child.on('exit',(code,signal)=>{process.exitCode=code??(signal==='SIGINT'?0:1)})
}catch(error){console.error(error.message);process.exitCode=1}
