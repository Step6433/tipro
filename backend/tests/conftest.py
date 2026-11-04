import os
import secrets
import subprocess
import sys
from pathlib import Path
import uuid
import asyncpg
import httpx
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import Settings, get_settings
base=Settings()
ADMIN_URL=make_url(os.environ.get('TEST_DATABASE_URL',base.database_url))
TEST_NAME='tipro_test_'+uuid.uuid4().hex[:12]
TEST_URL=ADMIN_URL.set(database=TEST_NAME)
os.environ['DATABASE_URL']=TEST_URL.render_as_string(hide_password=False)
os.environ['ALLOW_ADMIN_REGISTRATION']='true'
os.environ['ALLOW_DEMO_CONTROLS']='true'
os.environ['DEMO_DELAY_SECONDS']='0.02'
os.environ['DEMO_PASSWORD']=secrets.token_urlsafe(20)
get_settings.cache_clear()
from app.main import app, attempts
from app.database import engine

async def connect(database):
    return await asyncpg.connect(host=ADMIN_URL.host,port=ADMIN_URL.port or 5432,user=ADMIN_URL.username,password=ADMIN_URL.password,database=database)

@pytest_asyncio.fixture(scope='session',autouse=True)
async def test_database():
    admin=await connect('postgres')
    await admin.execute('CREATE DATABASE "'+TEST_NAME+'"')
    await admin.close()
    try:
        subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=os.environ.copy(),check=True,capture_output=True,text=True)
        yield
    finally:
        await engine.dispose()
        admin=await connect('postgres')
        await admin.execute('DROP DATABASE "'+TEST_NAME+'" WITH (FORCE)')
        await admin.close()

@pytest_asyncio.fixture(autouse=True)
async def isolated_data(test_database):
    if not TEST_NAME.startswith('tipro_test_'):raise RuntimeError('Refusing to clear a non-test DB')
    async with engine.begin() as c:
        await c.execute(text('TRUNCATE payment_webhook_events, auth_sessions, payments, qr_links, tip_goals, employees, merchants, demo_seed_records RESTART IDENTITY CASCADE'))
    attempts.clear()

@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        yield client
