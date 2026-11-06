"""Idempotent opt-in demo data. Never updates existing accounts or payments."""
import asyncio
import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select, update, text
from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import Merchant, Employee, Goal, QrLink, Payment, SeedRecord, utcnow
from app.core.security import hash_password, sign_model_qr
from app.services.payments import advisory_lock

async def seeded(db,key,model,create):
    record=await db.get(SeedRecord,key)
    if record:
        entity=await db.get(model,record.entity_id)
        if not entity:raise RuntimeError(f'Seed record {key} points to a missing entity; refusing to recreate it silently.')
        return entity,False
    entity=await create()
    db.add(entity);await db.flush()
    primary=next(iter(model.__table__.primary_key.columns)).name
    db.add(SeedRecord(key=key,entity_id=getattr(entity,primary)))
    await db.flush();return entity,True

async def seed():
    settings=get_settings()
    if not settings.demo_password or len(settings.demo_password.get_secret_value())<12:raise RuntimeError('Set DEMO_PASSWORD (12+ characters) in backend/.env before seeding.')
    hashed=await hash_password(settings.demo_password.get_secret_value())
    async with SessionLocal() as db:
        await advisory_lock(db,'tipro-seed-v1')
        async def account(key,**fields):
            async def create():
                if await db.scalar(select(Employee.employee_id).where(Employee.auth_email==fields['auth_email'])):raise RuntimeError('A demo login already belongs to an existing account; nothing was overwritten.')
                return Employee(**fields,password_hash=hashed,password=None,payment_details='',active=True,login=fields['auth_email'])
            return (await seeded(db,key,Employee,create))[0]
        await account('seed-admin',name='Администратор платформы',merchant_id=None,position='manager',platform_admin=True,title='Администратор',auth_email='admin@tipro.example.com')
        for index,(name,currency,language,city) in enumerate([
            ('Вкус-Сервис · Бангкок','THB','th','Бангкок'),('Вкус-Сервис · Сингапур','SGD','en','Сингапур'),('Вкус-Сервис · Ханой','VND','vi','Ханой'),
        ],1):
            async def make_merchant():return Merchant(name=name,status='ACTIVE',currency=currency,language=language,description=city,contact_email=f'manager{index}@tipro.example.com')
            m,_=await seeded(db,f'seed-merchant-{index}',Merchant,make_merchant)
            await account(f'seed-manager-{index}',name=f'Менеджер {city}',merchant_id=m.merchant_id,position='manager',platform_admin=False,title='Менеджер',auth_email=f'manager{index}@tipro.example.com')
            workers=[]
            for number,worker_name in enumerate(['Анна Смирнова','Иван Петров'],1):
                e=await account(f'seed-worker-{index}-{number}',name=worker_name,merchant_id=m.merchant_id,position='worker',platform_admin=False,title='Официант',auth_email=f'worker{index}{number}@tipro.example.com')
                workers.append(e)
                async def make_goal():return Goal(employee_id=e.employee_id,title='На путешествие',target=Decimal(5000000 if currency=='VND' else 50000),raised=0,currency=currency,active=True,created_at=utcnow()-timedelta(days=31))
                await seeded(db,f'seed-goal-{index}-{number}',Goal,make_goal)
            for number,e in enumerate(workers,1):
                async def make_qr():
                    token=str(secrets.randbits(256));created=utcnow().replace(microsecond=0);expires=created+timedelta(hours=24)
                    receipt_id=await db.scalar(text("SELECT nextval('receipt_id_seq')"))
                    q=QrLink(merchant_id=m.merchant_id,employee_id=e.employee_id,receipt_id=receipt_id,receipt_number=str(receipt_id),bill_amount=Decimal(100000 if currency=='VND' else 1000),currency=currency,nonce=token,exp=str(int(expires.timestamp())),signature='',token_version='v3',created_at=created,expires_at=expires,active=True,label=f'QR сотрудника · {city}')
                    q.signature=sign_model_qr(q)
                    return q
                await seeded(db,f'seed-qr-v3-{index}-{number}',QrLink,make_qr)
            for day in range(30):
                for number,e in enumerate(workers,1):
                    key=f'seed-payment-{index}-{day}-{number}'
                    if await db.get(SeedRecord,key):continue
                    goal=await db.scalar(select(Goal).where(Goal.employee_id==e.employee_id,Goal.active.is_(True)))
                    created=utcnow()-timedelta(days=day,hours=number)
                    tip=Decimal((day%5+1)*(10000 if currency=='VND' else 50))
                    status='DECLINED' if day%11==0 else 'CANCELED' if day%13==0 else 'PENDING' if day%17==0 else 'SUCCESS'
                    async def make_payment():return Payment(merchant_id=m.merchant_id,employee_id=e.employee_id,amount=Decimal(0),tip=tip,currency=currency,status=status,timestamp=created.isoformat(),created_at=created,updated_at=created,qr_id=None,goal_id=goal.goal_id if goal else None,external_id=None,public_token=None,provider='legacy',provider_outcome='pending',provider_due_at=None)
                    await seeded(db,key,Payment,make_payment)
                    if status=='SUCCESS' and goal:await db.execute(update(Goal).where(Goal.goal_id==goal.goal_id).values(raised=Goal.raised+tip))
        await db.commit()
    print('Demo data ready. Re-running does not overwrite data. Password is DEMO_PASSWORD in backend/.env.')

if __name__=='__main__':
    async def main():
        try:await seed()
        finally:await engine.dispose()
    asyncio.run(main())
