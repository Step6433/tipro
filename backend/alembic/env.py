import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool
from app.config import get_settings
from app.models import Base

config=context.config
target_metadata=Base.metadata

def migrate(connection):
    context.configure(connection=connection,target_metadata=target_metadata,compare_type=True)
    with context.begin_transaction():context.run_migrations()

async def online():
    engine=create_async_engine(get_settings().database_url,poolclass=pool.NullPool)
    async with engine.connect() as connection:await connection.run_sync(migrate)
    await engine.dispose()

if context.is_offline_mode():
    raise RuntimeError('These migrations inspect and preserve existing Users.sql tables; use online mode.')
else:asyncio.run(online())
