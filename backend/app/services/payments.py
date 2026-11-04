import hmac
import hashlib
import json
import secrets
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, text
from app.core.errors import ApiError
from app.core.money import money, percent_tip
from app.models import Payment, Employee, Goal, QrLink, utcnow
from app.core.security import sign_qr, parse_qr_token
from app.routers.qrs import resolve_qr
from app.services.providers import PROVIDERS, CheckoutRequest

async def advisory_lock(db, key):
    # PostgreSQL transaction lock serializes identical idempotency keys across workers.
    lock = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'big', signed=True)
    await db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key':lock})

async def transition(db, payment, status):
    if status == 'PENDING': return payment
    if payment.status != 'PENDING':
        if payment.status != status: raise ApiError('Платёж уже завершён с другим статусом.','CONFLICT',409)
        return payment
    if payment.qr_expires_at and payment.qr_expires_at <= utcnow():
        status = 'DECLINED'
        payment.failure_reason = 'QR_EXPIRED'
    if status == 'SUCCESS' and payment.qr_id:
        qr = await db.scalar(select(QrLink).where(QrLink.qr_id == payment.qr_id).with_for_update())
        if not qr or not qr.active or qr.nonce != payment.qr_nonce:
            status = 'DECLINED'
            payment.failure_reason = 'QR_USED'
        elif not hmac.compare_digest(qr.signature, sign_qr(qr.nonce,qr.exp)):
            status = 'DECLINED'
            payment.failure_reason = 'INVALID_QR'
        elif (qr.expires_at and qr.expires_at <= utcnow()) or (int(qr.exp) != 0 and int(qr.exp) <= utcnow().timestamp()):
            status = 'DECLINED'
            payment.failure_reason = 'QR_EXPIRED'
        # Permanent restaurant QR remains unchanged for other visitors.
    payment.status=status;payment.updated_at=utcnow()
    if status=='SUCCESS' and payment.goal_id:
        # This runs only while holding the payment row lock; each payment credits once.
        await db.execute(update(Goal).where(Goal.goal_id==payment.goal_id,Goal.employee_id==payment.employee_id,Goal.currency==payment.currency).values(raised=Goal.raised+payment.tip))
    await db.flush()
    return payment

async def reconcile(db,payment):
    if payment.status=='PENDING':
        if payment.qr_expires_at and payment.qr_expires_at <= utcnow():
            return await transition(db,payment,'DECLINED')
        status=await PROVIDERS[payment.provider].status(payment.external_id,payment.provider_outcome,payment.provider_due_at)
        await transition(db,payment,status)
    return payment

async def create_payment(db,token,body,idempotency_key):
    if not idempotency_key or len(idempotency_key)>120 or len(idempotency_key)<8:
        raise ApiError('Нужен Idempotency-Key длиной от 8 до 120 символов.')
    await advisory_lock(db,'payment:'+idempotency_key)
    nonce, exp, signature = parse_qr_token(token)
    # Recover an existing payment without extending its original session deadline.
    existing=await db.scalar(select(Payment).where(Payment.idempotency_key==idempotency_key).with_for_update())
    if existing:
        if existing.qr_nonce != nonce or (int(exp) != 0 and existing.qr_expires_at != datetime.fromtimestamp(int(exp), timezone.utc)):
            raise ApiError('Этот Idempotency-Key уже использован с другими данными.','CONFLICT',409)
        qr=await db.get(QrLink,existing.qr_id)
        merchant=None
    else:
        qr,merchant=await resolve_qr(db,token,lock=True)
    if body.currency!=qr.currency:raise ApiError('Валюта не совпадает с валютой QR-кода.')
    e=await db.scalar(select(Employee).where(Employee.employee_id==body.employee_id).with_for_update())
    if not e or not e.active or e.position!='worker' or e.merchant_id!=qr.merchant_id or (qr.employee_id and e.employee_id!=qr.employee_id):raise ApiError('Выберите активного сотрудника этого ресторана.','INVALID_EMPLOYEE',400)
    if body.percent is not None:
        if not qr.bill_amount:raise ApiError('В чеке не указана сумма для расчёта процента.')
        amount=percent_tip(qr.bill_amount,body.percent,qr.currency)
    else:amount=money(body.amount,qr.currency)
    payload={'qr':qr.qr_id,'employee':e.employee_id,'tip':str(amount),'currency':qr.currency,'scenario':body.scenario,'method':body.method}
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    if existing:
        if existing.request_fingerprint!=fingerprint:raise ApiError('Этот Idempotency-Key уже использован с другими данными.','CONFLICT',409)
        return existing,False
    goal=await db.scalar(select(Goal).where(Goal.employee_id==e.employee_id,Goal.active.is_(True),Goal.currency==qr.currency))
    intent=await PROVIDERS[body.method].create(CheckoutRequest(amount,qr.currency,idempotency_key,body.scenario))
    now=utcnow()
    payment=Payment(merchant_id=merchant.merchant_id,employee_id=e.employee_id,amount=qr.bill_amount or Decimal(0),tip=amount,status='PENDING',timestamp=now.isoformat(),currency=qr.currency,qr_id=qr.qr_id,qr_nonce=nonce,qr_expires_at=datetime.fromtimestamp(int(exp),timezone.utc) if int(exp) else now+timedelta(minutes=30),goal_id=goal.goal_id if goal else None,external_id=intent.external_id,public_token=secrets.token_urlsafe(32),idempotency_key=idempotency_key,request_fingerprint=fingerprint,provider=body.method,provider_outcome=intent.outcome,provider_due_at=intent.due_at,created_at=now,updated_at=now)
    db.add(payment);await db.flush();return payment,True

async def public_payment(db,token):
    p=await db.scalar(select(Payment).where(Payment.public_token==token).with_for_update())
    if not p:raise ApiError('Платёж не найден.','NOT_FOUND',404)
    return p
