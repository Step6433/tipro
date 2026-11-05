"""Start/stop an isolated developer PostgreSQL cluster, optionally restore a custom dump.
Never attaches to or overwrites a pre-existing system database.
"""
import argparse
import asyncio
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import asyncpg
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--bin-dir',required=True)
parser.add_argument('--restore',type=Path)
parser.add_argument('--stop',action='store_true')
args=parser.parse_args()
values=dotenv_values(ROOT/'.env');url=make_url(values['DATABASE_URL'])
if url.host not in ['127.0.0.1','localhost']:raise SystemExit('This helper is only for an isolated local database.')
for value in [url.username,url.database]:
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',value or ''):raise SystemExit('Use simple local DB/user identifiers.')
bin_dir=Path(args.bin_dir);runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
data=runtime/'pgdata';log=runtime/'postgres.log'
def executable(name):return bin_dir/(name+'.exe' if os.name=='nt' else name)
def command(name,*arguments,**kwargs):return subprocess.run([str(executable(name)),*map(str,arguments)],check=True,**kwargs)
if args.stop:
    command('pg_ctl','-D',data,'stop','-m','fast');raise SystemExit()
if not (data/'PG_VERSION').exists():
    pwfile=runtime/'init-password'
    fd=os.open(pwfile,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as output:output.write(url.password+'\n')
    try:command('initdb','-D',data,'-U',url.username,'--auth=scram-sha-256','--pwfile='+str(pwfile),'--encoding=UTF8','--locale=C',stdout=subprocess.DEVNULL)
    finally:pwfile.unlink(missing_ok=True)
status=subprocess.run([str(executable('pg_ctl')),'-D',str(data),'status'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if status.returncode:
    server_options=f'-h 127.0.0.1 -p {url.port or 5432}'
    if os.name!='nt':server_options+=' -k '+shlex.quote(str(runtime))
    command('pg_ctl','-D',data,'-l',log,'-o',server_options, '-w','start',stdout=subprocess.DEVNULL)
async def prepare():
    conn=await asyncpg.connect(host=url.host,port=url.port or 5432,user=url.username,password=url.password,database='postgres')
    exists=await conn.fetchval('SELECT 1 FROM pg_database WHERE datname=$1',url.database)
    if not exists:await conn.execute('CREATE DATABASE "'+url.database+'"')
    await conn.close()
    conn=await asyncpg.connect(host=url.host,port=url.port or 5432,user=url.username,password=url.password,database=url.database)
    tables=await conn.fetchval("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
    await conn.close()
    return tables
count=asyncio.run(prepare())
if args.restore:
    if count:raise SystemExit('Target DB is not empty; restore refused. Existing data were left unchanged.')
    if args.restore.read_bytes()[:5]!=b'PGDMP':raise SystemExit('Expected a PostgreSQL custom dump, not SQL text.')
    env={**os.environ,'PGPASSWORD':url.password}
    command('pg_restore','--no-owner','--no-acl','--exit-on-error','-h',url.host,'-p',url.port or 5432,'-U',url.username,'-d',url.database,args.restore,env=env)
print(f'Isolated PostgreSQL ready on {url.host}:{url.port or 5432}; database {url.database}.')
