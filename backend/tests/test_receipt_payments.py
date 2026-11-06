"""Acceptance checks for receipt-bound payments and their authorization boundaries."""
import asyncio
import uuid
from decimal import Decimal
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models import QrLink, AuditEvent, Payment, Merchant, Employee
from tests.test_api import fixture, auth, register, finish, PASSWORD

async def prepare(client,qr,e,**overrides):
    body={'employeeId':int(e['id']),'receiptId':int(qr['receipt']['id']),'amount':'31.85','currency':qr['currency'],'scenario':'success',**overrides}
    return await client.post('/api/public/qrs/'+qr['id']+'/payments',headers={'Idempotency-Key':str(uuid.uuid4())},json=body)

async def new_qr(client,owner,e,bill='637',**fields):
    response=await client.post('/api/qrs',headers=auth(owner),json={'employeeId':int(e['id']),'billAmount':bill,**fields})
    assert response.status_code==201,response.text
    return response.json()

async def test_creation_is_not_payment_confirmation_and_cancel_is_audited(client):
    owner,worker,e,_=await fixture(client)
    qr=await new_qr(client,owner,e)
    response=await prepare(client,qr,e)
    assert response.status_code==201,response.text
    payment=response.json();assert payment['status']=='created'
    assert Decimal(payment['amountTotal'])==Decimal('668.85')
    await asyncio.sleep(.04)
    assert (await client.get('/api/public/payments/'+payment['publicToken'])).json()['status']=='created'
    async with SessionLocal() as db:
        saved=await db.get(Payment,int(payment['id']));assert saved.external_id is None
    canceled=await client.post('/api/public/payments/'+payment['publicToken']+'/cancel')
    assert canceled.status_code==200 and canceled.json()['status']=='cancelled'
    assert (await client.post('/api/public/payments/'+payment['publicToken']+'/cancel')).status_code==200
    again=await client.post('/api/public/payments/'+payment['publicToken']+'/confirm')
    assert again.json()['status']=='cancelled'
    events=(await client.get('/api/admin/audit',headers=auth(owner),params={'payment_id':payment['id']})).json()['items']
    assert [(r['fromStatus'],r['toStatus']) for r in reversed(events)]==[(None,'CREATED'),('CREATED','CANCELED')]
    assert all(r['actor']=='client' and r['qrId'] and r['at'] for r in events)
    assert (await client.get('/api/admin/audit',headers=auth(worker))).status_code==403
    other=await register(client,'other-audit@example.com')
    assert (await client.get('/api/admin/audit',headers=auth(other),params={'payment_id':payment['id']})).json()['total']==0

async def test_confirm_once_success_amount_and_pending_cancellation(client):
    owner,worker,e,_=await fixture(client)
    qr=await new_qr(client,owner,e)
    await client.post(f"/api/employees/{e['id']}/goals",headers=auth(worker),json={'title':'Dream','target':'1000','currency':'RUB'})
    payment=(await prepare(client,qr,e,percent='5',amount=None)).json()
    # Simultaneous confirmation must not create a second provider intent or credit.
    path='/api/public/payments/'+payment['publicToken']
    confirmations=await asyncio.gather(*(client.post(path+'/confirm') for _ in range(3)))
    assert all(r.status_code==200 for r in confirmations)
    result=await finish(client,payment)
    assert result['status']=='success' and Decimal(result['amount'])==Decimal('31.85')
    assert Decimal(result['amountTotal'])==Decimal('668.85')
    canceled=await client.post(path+'/cancel')
    assert canceled.status_code==409 and canceled.json()['code']=='CANCEL_NOT_ALLOWED'
    async with SessionLocal() as db:
        events=list((await db.scalars(select(AuditEvent).where(AuditEvent.payment_id==int(payment['id'])).order_by(AuditEvent.event_id))).all())
        assert [r.to_status for r in events]==['CREATED','PENDING','SUCCESS']
    detail=(await client.get('/api/employees/'+e['id'],headers=auth(worker))).json()
    assert Decimal(detail['goal']['raised'])==Decimal('31.85')
    qr2=await new_qr(client,owner,e)
    pending=(await prepare(client,qr2,e,scenario='pending')).json()
    await client.post('/api/public/payments/'+pending['publicToken']+'/confirm')
    denied=await client.post('/api/public/payments/'+pending['publicToken']+'/cancel')
    assert denied.status_code==409 and denied.json()['code']=='CANCEL_NOT_ALLOWED'

async def test_receipt_unique_and_amount_limits_including_zero(client):
    owner,worker,e,_=await fixture(client)
    qr=await new_qr(client,owner,e,receiptNumber='case-receipt')
    duplicate=await client.post('/api/qrs',headers=auth(owner),json={'employeeId':int(e['id']),'billAmount':'637','receiptNumber':'case-receipt'})
    assert duplicate.status_code==409
    for value in ['0','-1','1000000.01']:
        r=await client.post('/api/qrs',headers=auth(owner),json={'employeeId':int(e['id']),'billAmount':value})
        assert r.status_code==422 and r.json()['code']=='AMOUNT_OUT_OF_RANGE'
    wrong=await prepare(client,qr,e,receiptId=int(qr['receipt']['id'])+1)
    assert wrong.status_code==422 and wrong.json()['code']=='RECEIPT_MISMATCH'
    for changes in [{'amount':'318.51'},{'percent':'50.01','amount':None},{'percent':'-1','amount':None}]:
        response=await prepare(client,qr,e,**changes)
        assert response.status_code==422 and response.json()['code']=='TIP_OUT_OF_RANGE',response.text
    for pct in ['0','50']:
        fresh=await new_qr(client,owner,e)
        response=await prepare(client,fresh,e,percent=pct,amount=None)
        assert response.status_code==201,response.text
        assert Decimal(response.json()['amount'])==Decimal('637')*Decimal(pct)/100
        await client.post('/api/public/payments/'+response.json()['publicToken']+'/confirm')
        assert (await finish(client,response.json()))['status']=='success'

async def test_signature_authenticates_all_identifiers_and_db_binding(client):
    owner,worker,e,qr=await fixture(client)
    fields=qr['id'].split('.')
    assert len(fields)==6
    for i in range(5):
        changed=fields.copy();changed[i]=str(int(changed[i])+1)
        response=await client.get('/api/public/qrs/'+'.'.join(changed))
        assert response.status_code==422 and response.json()['code']=='INVALID_QR'
    async with SessionLocal() as db:
        q=await db.scalar(select(QrLink).where(QrLink.nonce==qr['nonce']))
        q.receipt_id+=1000;await db.commit()
    assert (await client.get('/api/public/qrs/'+qr['id'])).status_code==422

async def test_platform_block_during_payment_prevents_credit_and_unblocks(client):
    owner,worker,e,qr=await fixture(client)
    payment=(await prepare(client,qr,e,scenario='pending')).json()
    await client.post('/api/public/payments/'+payment['publicToken']+'/confirm')
    admin=(await client.post('/api/auth/login',json={'email':'approval-admin@example.com','password':PASSWORD})).json()
    path='/api/admin/restaurants/'+owner['session']['merchantId']
    assert (await client.post(path+'/block',headers=auth(owner))).status_code==403
    assert (await client.post(path+'/block',headers=auth(admin))).status_code==200
    assert (await client.get('/api/workspace',headers=auth(owner))).json()['code']=='MERCHANT_BLOCKED'
    assert (await client.post('/api/auth/logout',headers=auth(worker))).status_code==204
    denied=await client.get('/api/public/qrs/'+qr['id'])
    assert denied.status_code==403 and denied.json()['code']=='MERCHANT_BLOCKED'
    from app.services.payments import transition
    async with SessionLocal() as db:
        p=await db.scalar(select(Payment).where(Payment.payment_id==int(payment['id'])).with_for_update())
        await transition(db,p,'SUCCESS');await db.commit()
    result=(await client.get('/api/public/payments/'+payment['publicToken'])).json()
    assert result['status']=='declined' and result['errorCode']=='MERCHANT_BLOCKED'
    assert (await client.post(path+'/unblock',headers=auth(admin))).json()['status']=='ACTIVE'
    assert (await client.get('/api/workspace',headers=auth(owner))).status_code==200
    qr2=await new_qr(client,owner,e)
    before=(await prepare(client,qr2,e)).json()
    await client.post(path+'/block',headers=auth(admin))
    assert (await client.post('/api/public/payments/'+before['publicToken']+'/confirm')).json()['errorCode']=='MERCHANT_BLOCKED'

async def test_payment_details_only_accept_masks_in_api_and_database(client):
    owner,worker,e,qr=await fixture(client)
    for value in ['4111111111111111','1234','****123','text']:
        response=await client.patch('/api/employees/'+e['id'],headers=auth(owner),json={'name':e['name'],'role':e['role'],'paymentDetails':value})
        assert response.status_code==422
    response=await client.patch('/api/employees/'+e['id'],headers=auth(owner),json={'name':e['name'],'role':e['role'],'paymentDetails':'****1234'})
    assert response.json()['paymentDetails']=='****1234'
    assert 'paymentDetails' not in (await client.get('/api/public/qrs/'+qr['id'])).json()['employees'][0]
    async with SessionLocal() as db:
        try:
            await db.execute(text("UPDATE employees SET payment_details='4111111111111111' WHERE employee_id=:id"),{'id':int(e['id'])})
            await db.commit()
            assert False,'Database accepted unmasked details'
        except IntegrityError:await db.rollback()

async def test_report_metrics_match_successful_receipt_payments(client):
    owner,worker,e,_=await fixture(client)
    for scenario in ['success','declined']:
        qr=await new_qr(client,owner,e)
        p=(await prepare(client,qr,e,scenario=scenario)).json()
        await client.post('/api/public/payments/'+p['publicToken']+'/confirm');await finish(client,p)
    stats=(await client.get('/api/analytics?timezone=Europe/Moscow',headers=auth(worker))).json()
    metric=stats['totals'][0]
    assert metric['count']==2 and metric['successful']==1
    assert Decimal(metric['avgTipPct'])==5 and Decimal(metric['successRate'])==Decimal('.5')
    assert Decimal(metric['average'])==Decimal('31.85') and metric['topDay']==stats['series'][0]['date']
    assert Decimal(stats['series'][0]['avgTipPct'])==5

async def test_half_percent_rounding_never_exceeds_half_of_bill(client):
    owner,worker,e,_=await fixture(client)
    qr=await new_qr(client,owner,e,bill='0.01')
    response=await prepare(client,qr,e,percent='50',amount=None)
    assert response.status_code==201,response.text
    assert Decimal(response.json()['amount'])==0

async def test_public_rate_limit_and_error_retryability(client):
    owner,worker,e,qr=await fixture(client)
    invalid=await client.get('/api/public/qrs/'+qr['id']+'bad')
    assert invalid.status_code==422 and invalid.json()['retryable'] is False
    from app.main import attempts
    from time import monotonic
    from collections import deque
    attempts['public:127.0.0.1']=deque([monotonic()]*300)
    limited=await client.get('/api/public/qrs/'+qr['id'])
    assert limited.status_code==429 and limited.json()['code']=='RATE_LIMIT'
