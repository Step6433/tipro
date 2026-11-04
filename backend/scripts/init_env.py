"""Generate local secrets without printing them or overwriting an existing .env."""
import argparse
import os
from pathlib import Path
import secrets
parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=5432)
args=parser.parse_args()
path=Path(__file__).resolve().parents[1]/'.env'
if path.exists():
    print('backend/.env already exists; left unchanged.')
else:
    password=secrets.token_urlsafe(32)
    lines=[f'DATABASE_URL=postgresql+asyncpg://tipro:{password}@127.0.0.1:{args.port}/tipro',f'JWT_SECRET={secrets.token_urlsafe(48)}',f'WEBHOOK_SECRET={secrets.token_urlsafe(48)}','FRONTEND_URL=http://localhost:5173','CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:5174"]','COOKIE_SECURE=false','ALLOW_DEMO_CONTROLS=true','ALLOW_ADMIN_REGISTRATION=false','LEGACY_CURRENCY=RUB',f'DEMO_PASSWORD={secrets.token_urlsafe(18)}','POSTGRES_USER=tipro',f'POSTGRES_PASSWORD={password}','POSTGRES_DB=tipro']
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as output:output.write('\n'.join(lines)+'\n')
    print('Created backend/.env with random secrets. No secrets were printed.')
