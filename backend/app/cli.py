import argparse
import asyncio
import getpass
import os
from sqlalchemy import select
from app.database import SessionLocal, engine
from app.models import Employee
from app.core.security import hash_password

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['create-admin'])
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',default='Администратор платформы')
    args=parser.parse_args()
    password=os.environ.get('ADMIN_PASSWORD') or getpass.getpass('New admin password (12+ characters): ')
    if len(password)<12:raise SystemExit('Password must be at least 12 characters.')
    async with SessionLocal() as db:
        if await db.scalar(select(Employee.employee_id).where(Employee.auth_email==args.email.strip().lower())):raise SystemExit('This login already exists. No account was changed.')
        user=Employee(name=args.name,merchant_id=None,position='manager',platform_admin=True,title='Администратор',auth_email=args.email.strip().lower(),login=args.email.strip().lower(),password_hash=await hash_password(password),active=True,payment_details='')
        db.add(user);await db.commit()
    print('Administrator created. Password was not logged.')

if __name__=='__main__':
    async def run():
        try:await main()
        finally:await engine.dispose()
    asyncio.run(run())
