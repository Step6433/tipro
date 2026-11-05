import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, copyFileSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'

test('clean checkout bootstrap creates its own venv and preserves settings on repeat launch', {timeout:60000},()=>{
  const root=mkdtempSync(join(tmpdir(),'tipro launcher test '))
  try{
    for(const folder of ['scripts','backend/scripts','node_modules/vite/bin'])mkdirSync(join(root,folder),{recursive:true})
    copyFileSync(new URL('../scripts/run-python.mjs',import.meta.url),join(root,'scripts/run-python.mjs'))
    copyFileSync(new URL('../backend/scripts/init_env.py',import.meta.url),join(root,'backend/scripts/init_env.py'))
    // The fixture has no Python packages; it tests real bootstrap/install mechanics, not app dependencies.
    writeFileSync(join(root,'backend/requirements.lock'),'')
    writeFileSync(join(root,'node_modules/vite/bin/vite.js'),'')
    writeFileSync(join(root,'scripts/start.py'),"import sys,os\nfrom pathlib import Path\nassert Path(sys.prefix).name == '.venv'\nassert os.environ['PYTHONUTF8'] == '1'\nprint('BOOTSTRAP_READY')\n")
    const command=join(root,'scripts/run-python.mjs')
    const first=spawnSync(process.execPath,[command,'start','--no-open'],{cwd:root,encoding:'utf8',timeout:45000})
    assert.equal(first.status,0,first.stdout+'\n'+first.stderr)
    assert.ok(first.stdout.includes('BOOTSTRAP_READY'))
    const python=join(root,'backend/.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python')
    assert.ok(existsSync(python))
    const config=readFileSync(join(root,'backend/.env'),'utf8')
    assert.ok(config.includes('127.0.0.1:55432'))
    const repeat=spawnSync(process.execPath,[command,'start','--no-open'],{cwd:root,encoding:'utf8',timeout:15000})
    assert.equal(repeat.status,0,repeat.stdout+'\n'+repeat.stderr)
    assert.ok(repeat.stdout.includes('BOOTSTRAP_READY'))
    assert.ok(!repeat.stdout.includes('Устанавливаю зависимости'))
    assert.equal(readFileSync(join(root,'backend/.env'),'utf8'),config)
  }finally{rmSync(root,{recursive:true,force:true})}
})
