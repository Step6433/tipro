import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import timedelta
from decimal import Decimal
import pytest
from sqlalchemy import text, select, func
from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import Payment, Goal, QrLink, AuthSession, utcnow
from app.seed import seed
from tests.conftest import connect, ADMIN_URL, ROOT

PASSWORD='CaseTest-Password-2026'

def auth(data):return {'Authorization':'Bearer '+data['accessToken']}
async def register(client,email='owner@example.com',role='merchant',**fields):
    body={'name':'Тестовый пользователь','email':email,'password':PASSWORD,'role':role}
    if role=='merchant':body['restaurantName']='Тестовый ресторан'
    body.update(fields)
    response=await client.post('/api/auth/register',json=body)
    assert response.status_code==201,response.text
    return response.json()

async def fixture(client,currency='RUB'):
    owner=await register(client)
    mid=owner['session']['merchantId']
    if currency!='RUB':
        r=await client.patch(f'/api/restaurants/{mid}/settings',headers=auth(owner),json={'currency':currency,'language':'en','tipPercentages':[5,10,15],'paymentMethods':['demo']});assert r.status_code==200,r.text
    r=await client.post('/api/employees',headers=auth(owner),json={'name':'Анна Смирнова','role':'Официант','active':True});assert r.status_code==201,r.text
    employee=r.json()
    qr=(await client.post('/api/qrs',headers=auth(owner),json={'receiptNumber':'1042','billAmount':'2800','currency':currency,'expiresInDays':1})).json()
    assert 'id' in qr,qr
    worker=await register(client,'anna@example.com','employee',invite=employee['accessToken'])
    return owner,worker,employee,qr

async def pay(client,qr,employee,amount='100',scenario='success',key=None,**extra):
    body={'employeeId':int(employee['id']),'currency':qr['currency'],'scenario':scenario,**extra}
    if 'percent' not in extra:body['amount']=amount
    return await client.post(f"/api/public/qrs/{qr['id']}/payments",headers={'Idempotency-Key':key or str(uuid.uuid4())},json=body)

async def finish(client,payment):
    await asyncio.sleep(.04)
    r=await client.get('/api/public/payments/'+payment['publicToken'])
    assert r.status_code==200,r.text
    return r.json()

async def test_registration_jwt_cookie_logout_and_argon2(client):
    owner=await register(client)
    settings=get_settings();settings.allow_admin_registration=False
    try:
        forbidden=await client.post('/api/auth/register',json={'role':'admin','name':'Not allowed','email':'forbidden@example.com','password':PASSWORD})
        assert forbidden.status_code==403
    finally:settings.allow_admin_registration=True
    me=await client.get('/api/auth/me');assert me.status_code==200
    assert me.json()['session']['role']=='merchant'
    assert 'HttpOnly' in (await client.post('/api/auth/login',json={'email':'owner@example.com','password':PASSWORD})).headers['set-cookie']
    async with engine.connect() as c:
        row=(await c.execute(text('SELECT password,password_hash FROM employees WHERE auth_email=:email'),{'email':'owner@example.com'})).one()
        assert row.password is None and row.password_hash.startswith('$argon2id$')
    assert (await client.post('/api/auth/login',json={'email':'owner@example.com','password':'wrong'})).status_code==401
    assert (await client.get('/api/auth/me',headers={'Authorization':'Bearer invalid'})).status_code==401
    assert (await client.post('/api/auth/logout',headers=auth(owner))).status_code==204
    assert (await client.get('/api/auth/me',headers=auth(owner))).status_code==401
    assert (await client.get('/api/auth/me')).status_code==401

async def test_employee_invitation_once_and_scoped_permissions(client):
    owner,worker,e,qr=await fixture(client)
    assert (await client.get('/api/auth/invitations/'+e['accessToken'])).status_code==400
    duplicate=await client.post('/api/auth/register',json={'role':'employee','name':'Другой','email':'duplicate@example.com','password':PASSWORD,'invite':e['accessToken']})
    assert duplicate.status_code==400
    rows=(await client.get('/api/employees',headers=auth(worker))).json()['items']
    assert [row['id'] for row in rows]==[e['id']]
    assert 'accessToken' not in rows[0]
    assert (await client.post('/api/qrs',headers=auth(worker),json={'receiptNumber':'1','billAmount':'100'})).status_code==403
    assert (await client.post('/api/employees',headers=auth(worker),json={'name':'Чужой','role':'Бармен'})).status_code==403
    assert (await client.get('/api/admin/overview',headers=auth(worker))).status_code==403
    other=await register(client,'other@example.com')
    assert (await client.get('/api/employees/'+e['id'],headers=auth(other))).status_code==403
    assert (await client.get('/api/payments',headers=auth(other))).json()['total']==0
    assert (await client.get('/api/restaurants/'+owner['session']['merchantId'],headers=auth(other))).status_code==403

async def test_public_qr_expiry_tampering_currency_and_employee(client):
    owner,worker,e,qr=await fixture(client,'THB')
    public=await client.get(f"/api/public/restaurants/{qr['merchantId']}?qr={qr['id']}")
    assert public.status_code==200
    body=public.json();assert body['employees'][0]['id']==e['id'];assert 'email' not in body['merchant'];assert 'accessToken' not in body['employees'][0]
    assert (await client.get('/api/public/qrs/'+qr['id']+'x')).status_code==404
    assert (await client.get(f"/api/public/restaurants/999?qr={qr['id']}")).status_code==404
    assert (await pay(client,qr,{'id':'999'})).status_code==400
    assert (await pay(client,qr,e,currency='SGD')).status_code==400
    async with SessionLocal() as db:
        q=await db.scalar(select(QrLink).where(QrLink.nonce==qr['nonce']));q.expires_at=utcnow()-timedelta(seconds=1);await db.commit()
    assert (await client.get('/api/public/qrs/'+qr['id'])).status_code==404

async def test_goal_success_and_idempotency_credit_exactly_once(client):
    owner,worker,e,qr=await fixture(client,'SGD')
    goal=(await client.post(f"/api/employees/{e['id']}/goals",headers=auth(worker),json={'title':'Обучение','target':'1000.50','currency':'SGD'})).json()['goal']
    key=str(uuid.uuid4())
    first=await pay(client,qr,e,'12.35',key=key);assert first.status_code==201,first.text
    assert first.json()['status']=='pending'
    second=await pay(client,qr,e,'12.35',key=key);assert second.status_code==200
    assert first.json()['id']==second.json()['id']
    assert (await pay(client,qr,e,'20',key=key)).status_code==409
    result=await finish(client,first.json());assert result['status']=='success';assert Decimal(result['amount'])==Decimal('12.35')
    await finish(client,first.json())
    detail=(await client.get('/api/employees/'+e['id'],headers=auth(worker))).json()
    assert Decimal(detail['goal']['raised'])==Decimal('12.35')
    history=(await client.get('/api/payments?currency=SGD',headers=auth(worker))).json()
    assert history['total']==1
    stats=(await client.get('/api/analytics?currency=SGD',headers=auth(owner))).json()
    assert Decimal(stats['totals'][0]['total'])==Decimal('12.35')
    assert stats['series'][0]['count']==1

async def test_concurrent_idempotency_requests(client):
    owner,worker,e,qr=await fixture(client)
    key=str(uuid.uuid4())
    results=await asyncio.gather(*(pay(client,qr,e,'200',key=key) for _ in range(4)))
    assert all(r.status_code in [200,201] for r in results),[r.text for r in results]
    assert len({r.json()['id'] for r in results})==1
    async with engine.connect() as c:assert await c.scalar(select(func.count()).select_from(Payment))==1

async def test_pending_declined_cancelled_percent_and_fraction_digits(client):
    owner,worker,e,qr=await fixture(client,'THB')
    await client.post(f"/api/employees/{e['id']}/goals",headers=auth(worker),json={'title':'Мечта','target':'2000','currency':'THB'})
    for scenario,expected in [('declined','declined'),('cancelled','cancelled')]:
        created=await pay(client,qr,e,'20',scenario);assert created.status_code==201
        assert (await finish(client,created.json()))['status']==expected
    pending=(await pay(client,qr,e,'100','pending')).json()
    assert (await finish(client,pending))['status']=='pending'
    assert (await client.post('/api/public/payments/'+pending['publicToken']+'/cancel')).json()['status']=='cancelled'
    percent=await pay(client,qr,e,percent='10');assert percent.status_code==201,percent.text
    assert Decimal(percent.json()['amount'])==Decimal('280')
    assert (await pay(client,qr,e,'1.001')).status_code==400
    assert (await pay(client,qr,e,'0')).status_code==400
    assert (await pay(client,qr,e,'NaN')).status_code==422

async def test_webhook_signature_replay_and_goal_credit(client):
    owner,worker,e,qr=await fixture(client)
    await client.post(f"/api/employees/{e['id']}/goals",headers=auth(worker),json={'title':'Мечта','target':'2000','currency':'RUB'})
    pending=(await pay(client,qr,e,'50','pending')).json()
    async with SessionLocal() as db:external=await db.scalar(select(Payment.external_id).where(Payment.payment_id==int(pending['id'])))
    event={'event_id':'event-1','external_id':external,'status':'success','amount':'50','currency':'RUB'}
    raw=json.dumps(event).encode();stamp=str(int(time.time()))
    signature=hmac.new(get_settings().webhook_secret.get_secret_value().encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    headers={'Content-Type':'application/json','X-Webhook-Timestamp':stamp,'X-Webhook-Signature':signature}
    assert (await client.post('/api/webhooks/demo',content=raw,headers={**headers,'X-Webhook-Signature':'bad'})).status_code==401
    r=await client.post('/api/webhooks/demo',content=raw,headers=headers);assert r.status_code==200,r.text
    assert (await client.post('/api/webhooks/demo',content=raw,headers=headers)).json()['duplicate'] is True
    assert (await finish(client,pending))['status']=='success'
    detail=(await client.get('/api/employees/'+e['id'],headers=auth(worker))).json()
    assert Decimal(detail['goal']['raised'])==Decimal('50')
    expired_stamp=str(int(time.time())-301)
    assert (await client.post('/api/webhooks/demo',content=raw,headers={**headers,'X-Webhook-Timestamp':expired_stamp})).status_code==401

async def test_currency_aggregation_date_filter_csv_and_settings(client):
    owner,worker,e,qr=await fixture(client,'VND')
    assert (await pay(client,qr,e,'100.5')).status_code==400
    p=(await pay(client,qr,e,'100')).json();await finish(client,p)
    mid=owner['session']['merchantId']
    changed=await client.patch(f'/api/restaurants/{mid}/settings',headers=auth(owner),json={'currency':'SGD','language':'fil','tipPercentages':[3,7,12],'paymentMethods':['demo']});assert changed.status_code==200,changed.text
    q2=(await client.post('/api/qrs',headers=auth(owner),json={'receiptNumber':'2','billAmount':'125.50'})).json()
    p2=(await pay(client,q2,e,'3.25')).json();await finish(client,p2)
    stats=(await client.get('/api/analytics',headers=auth(owner))).json()
    totals={r['currency']:Decimal(r['total']) for r in stats['totals']}
    assert totals=={'VND':Decimal(100),'SGD':Decimal('3.25')}
    for bucket in ['day','week','month']:assert (await client.get('/api/analytics?bucket='+bucket,headers=auth(worker))).status_code==200
    assert (await client.get('/api/payments?start=2000-01-01&end=2000-01-02',headers=auth(owner))).json()['total']==0
    csv=await client.get('/api/payments/export?currency=SGD',headers=auth(worker));assert csv.status_code==200;assert 'SGD' in csv.text and 'VND' not in csv.text
    assert (await client.get('/api/payments?limit=1',headers=auth(owner))).json()['limit']==1

async def test_deactivation_expired_sessions_and_origin(client):
    owner,worker,e,qr=await fixture(client)
    assert (await client.patch('/api/employees/'+e['id'],headers=auth(owner),json={'name':e['name'],'role':e['role'],'active':False})).status_code==200
    assert (await client.get('/api/auth/me',headers=auth(worker))).status_code==401
    assert (await pay(client,qr,e)).status_code==400
    forbidden=await client.post('/api/auth/login',json={'email':'owner@example.com','password':PASSWORD},headers={'Origin':'https://attacker.invalid'})
    assert forbidden.status_code==403
    async with SessionLocal() as db:
        sessions=await db.scalars(select(AuthSession))
        for session in sessions:session.expires_at=utcnow()-timedelta(seconds=1)
        await db.commit()
    assert (await client.get('/api/auth/me',headers=auth(owner))).status_code==401

async def test_admin_scope_and_seed_is_idempotent(client):
    await seed()
    async with engine.connect() as c:before=[await c.scalar(text(f'SELECT count(*) FROM {t}')) for t in ['merchants','employees','payments','qr_links']]
    await seed()
    async with engine.connect() as c:after=[await c.scalar(text(f'SELECT count(*) FROM {t}')) for t in ['merchants','employees','payments','qr_links']]
    assert before==after
    login=await client.post('/api/auth/login',json={'email':'admin@tipro.example.com','password':get_settings().demo_password.get_secret_value()});assert login.status_code==200,login.text
    admin=login.json()
    assert (await client.get('/api/admin/overview',headers=auth(admin))).json()['restaurantCount']==3
    assert (await client.get('/api/restaurants?limit=1',headers=auth(admin))).json()['total']==3
    assert (await client.post('/api/qrs',headers=auth(admin),json={'receiptNumber':'1','billAmount':'10'})).status_code==403
    stats=(await client.get('/api/analytics',headers=auth(admin))).json()
    assert {r['currency'] for r in stats['totals']}=={'THB','SGD','VND'}

async def test_migration_preserves_legacy_rows_hashes_passwords_and_repairs_sequences():
    name='tipro_test_legacy_'+uuid.uuid4().hex[:8]
    admin=await connect('postgres');await admin.execute('CREATE DATABASE "'+name+'"');await admin.close()
    try:
        conn=await connect(name)
        await conn.execute((ROOT/'schema'/'legacy.sql').read_text())
        await conn.execute("INSERT INTO merchants(merchant_id,name,status) OVERRIDING SYSTEM VALUE VALUES(42,'Legacy','ACTIVE')")
        await conn.execute("INSERT INTO employees(employee_id,merchant_id,name,payment_details,position,login,password) OVERRIDING SYSTEM VALUE VALUES(90,42,'Legacy manager','','manager','legacy@example.com',$1)",PASSWORD)
        await conn.execute("INSERT INTO payments(merchant_id,employee_id,amount,tip,status,timestamp) VALUES(42,90,100,10,'SUCCESS','2025-01-02T03:04:05+07:00')")
        await conn.close()
        env={**os.environ,'DATABASE_URL':ADMIN_URL.set(database=name).render_as_string(hide_password=False)}
        proc=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env,capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr
        conn=await connect(name)
        assert await conn.fetchval('SELECT count(*) FROM payments')==1
        assert await conn.fetchval('SELECT count(*) FROM employees WHERE password IS NOT NULL')==0
        assert (await conn.fetchval('SELECT password_hash FROM employees')).startswith('$argon2id$')
        assert await conn.fetchval("INSERT INTO merchants(name,status,currency,language,tip_percentages,payment_methods) VALUES('New','ACTIVE','RUB','ru','[5]','[\"demo\"]') RETURNING merchant_id")>42
        date=await conn.fetchval('SELECT created_at FROM payments');assert date.hour==20 and date.day==1
        assert await conn.fetchval("SELECT count(*) FROM information_schema.columns WHERE table_name='qr_links' AND column_name='mecrhant_id'")==1
        await conn.close()
    finally:
        admin=await connect('postgres');await admin.execute('DROP DATABASE "'+name+'" WITH (FORCE)');await admin.close()

async def test_server_confirms_demo_without_browser_polling(client):
    from app.main import app
    owner,worker,e,qr=await fixture(client)
    async with app.router.lifespan_context(app):
        payment=(await pay(client,qr,e,'33.25')).json()
        assert payment['status']=='pending'
        await asyncio.sleep(.65)
        async with SessionLocal() as db:
            saved=await db.get(Payment,int(payment['id']))
            assert saved.status=='SUCCESS'
            assert saved.tip==Decimal('33.25')

async def test_qr_sign_covers_nonce_and_exp_and_database_tampering(client):
    owner,worker,e,qr=await fixture(client)
    nonce,exp,sign=qr['id'].split('.')
    assert (nonce,exp,sign)==(qr['nonce'],qr['exp'],qr['sign'])
    assert (await client.get('/api/public/qrs/'+f'{nonce}.{int(exp)+60}.{sign}')).status_code==404
    assert (await client.get('/api/public/qrs/'+f'{int(nonce)+1}.{exp}.{sign}')).status_code==404
    assert (await client.get('/api/public/qrs/'+nonce)).status_code==404
    async with SessionLocal() as db:
        q=await db.scalar(select(QrLink).where(QrLink.nonce==nonce))
        q.exp=str(int(exp)+60)
        await db.commit()
    assert (await client.get('/api/public/qrs/'+qr['id'])).status_code==404

async def test_permanent_qr_accepts_multiple_payments_and_keeps_signature(client):
    owner,worker,e,_=await fixture(client)
    response=await client.post('/api/qrs',headers=auth(owner),json={'label':'Стойка ресторана'})
    assert response.status_code==201,response.text
    qr=response.json()
    assert qr['exp']=='0' and qr['expiresAt'] is None and qr['receipt'] is None
    goal=(await client.post(f"/api/employees/{e['id']}/goals",headers=auth(worker),json={'title':'Мечта','target':'1000','currency':'RUB'})).json()['goal']
    key=str(uuid.uuid4())
    first=(await pay(client,qr,e,'10',key=key)).json()
    second=(await pay(client,qr,e,'20')).json()
    results=await asyncio.gather(finish(client,first),finish(client,second))
    assert [r['status'] for r in results]==['success','success']
    assert (await client.get('/api/public/qrs/'+qr['id'])).status_code==200
    retry=await pay(client,qr,e,'10',key=key)
    assert retry.status_code==200 and retry.json()['id']==first['id']
    refreshed=(await client.get('/api/qrs',headers=auth(owner))).json()['items'][0]
    assert refreshed['id']==qr['id'] and refreshed['sign']==qr['sign']
    detail=(await client.get('/api/employees/'+e['id'],headers=auth(worker))).json()
    assert Decimal(detail['goal']['raised'])==30
    image=await client.get('/api/qrs/'+qr['id']+'/image',headers=auth(owner))
    assert image.status_code==200 and image.content.startswith(b'\x89PNG')
    await client.patch('/api/qrs/'+qr['id'],headers=auth(owner),json={'active':False})
    assert (await pay(client,qr,e,'5')).status_code==404

async def test_expired_payment_session_rejects_late_webhook_without_goal_credit(client,monkeypatch):
    owner,worker,e,qr=await fixture(client)
    await client.post(f"/api/employees/{e['id']}/goals",headers=auth(worker),json={'title':'Цель','target':'1000','currency':'RUB'})
    p=(await pay(client,qr,e,'50','pending')).json()
    async with SessionLocal() as db:
        saved=await db.get(Payment,int(p['id']))
        external=saved.external_id
        deadline=saved.qr_expires_at
    monkeypatch.setattr('app.services.payments.utcnow',lambda:deadline+timedelta(seconds=1))
    event={'event_id':'late-event','external_id':external,'status':'success','amount':'50','currency':'RUB'}
    raw=json.dumps(event).encode();stamp=str(int(time.time()))
    signature=hmac.new(get_settings().webhook_secret.get_secret_value().encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    r=await client.post('/api/webhooks/demo',content=raw,headers={'Content-Type':'application/json','X-Webhook-Timestamp':stamp,'X-Webhook-Signature':signature})
    assert r.status_code==200,r.text
    result=await finish(client,p)
    assert result['status']=='declined' and result['errorCode']=='QR_EXPIRED'
    detail=(await client.get('/api/employees/'+e['id'],headers=auth(worker))).json()
    assert Decimal(detail['goal']['raised'])==0

async def test_worker_expires_pending_session_without_browser_polling(client):
    from app.main import app
    owner,worker,e,qr=await fixture(client)
    p=(await pay(client,qr,e,'10','pending')).json()
    async with SessionLocal() as db:
        saved=await db.get(Payment,int(p['id']))
        saved.qr_expires_at=utcnow()-timedelta(seconds=1)
        await db.commit()
    async with app.router.lifespan_context(app):
        await asyncio.sleep(.65)
    async with SessionLocal() as db:
        saved=await db.get(Payment,int(p['id']))
        assert saved.status=='DECLINED' and saved.failure_reason=='QR_EXPIRED'

@pytest.mark.parametrize('currency',['USD','EUR','CNY'])
async def test_international_currencies_and_restaurant_language(client,currency):
    owner,worker,e,_=await fixture(client,currency)
    mid=owner['session']['merchantId']
    updated=await client.patch(f'/api/restaurants/{mid}/settings',headers=auth(owner),json={'language':'zh'})
    assert updated.status_code==200,updated.text
    created=await client.post('/api/qrs',headers=auth(owner),json={'label':'International tips'})
    assert created.status_code==201,created.text
    qr=created.json()
    assert qr['currency']==currency
    public=(await client.get('/api/public/qrs/'+qr['id'])).json()
    assert public['merchant']['language']=='zh'
    await client.post(f"/api/employees/{e['id']}/goals",headers=auth(worker),json={'title':'Dream','target':'100','currency':currency})
    assert (await pay(client,qr,e,'12.345')).status_code==400
    pending=await pay(client,qr,e,'12.35')
    assert pending.status_code==201,pending.text
    assert (await finish(client,pending.json()))['status']=='success'
    detail=(await client.get('/api/employees/'+e['id'],headers=auth(worker))).json()
    assert Decimal(detail['goal']['raised'])==Decimal('12.35')
    stats=(await client.get('/api/analytics?currency='+currency,headers=auth(owner))).json()
    assert Decimal(stats['totals'][0]['total'])==Decimal('12.35')

async def test_project_sql_schema_restores_into_empty_database():
    name='tipro_test_snapshot_'+uuid.uuid4().hex[:8]
    admin=await connect('postgres');await admin.execute('CREATE DATABASE "'+name+'"');await admin.close()
    try:
        conn=await connect(name)
        try:
            await conn.execute((ROOT/'schema'/'tipro.sql').read_text())
            tables=set(await conn.fetchval("SELECT array_agg(tablename) FROM pg_tables WHERE schemaname='public'"))
            assert {'merchants','employees','payments','qr_links','tip_goals','auth_sessions','payment_webhook_events','demo_seed_records','alembic_version'}<=tables
            assert await conn.fetchval('SELECT count(*) FROM public.employees')==0
            assert await conn.fetchval('SELECT count(*) FROM public.payments')==0
            assert await conn.fetchval('SELECT version_num FROM public.alembic_version')=='0005_permanent_qr'
            assert await conn.fetchval("INSERT INTO public.merchants(name,status,currency,language,tip_percentages,payment_methods) VALUES('Snapshot test','ACTIVE','RUB','ru','[5]','[\"demo\"]') RETURNING merchant_id")>0
        finally:await conn.close()
        env={**os.environ,'DATABASE_URL':ADMIN_URL.set(database=name).render_as_string(hide_password=False)}
        proc=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env,capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr
    finally:
        admin=await connect('postgres');await admin.execute('DROP DATABASE "'+name+'" WITH (FORCE)');await admin.close()
