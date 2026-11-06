import hmac
import hashlib
import json
import secrets
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select, update, text
from app.core.errors import ApiError
from app.core.money import money, percent_tip
from app.models import Payment, Employee, Goal, QrLink, Merchant, utcnow
from app.core.security import sign_model_qr, parse_qr_token
from app.routers.qrs import resolve_qr
from app.services.providers import PROVIDERS, CheckoutRequest
from app.services.audit import record

async def advisory_lock(db, key):
    lock = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'big', signed=True)
    await db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key':lock})

async def transition(db, payment, status, actor='system'):
    previous=payment.status
    if status==previous:return payment
    if previous not in ('CREATED','PENDING'):
        raise ApiError('Платёж уже завершён.','CANCEL_NOT_ALLOWED' if status=='CANCELED' else 'CONFLICT',409)
    if status=='CANCELED' and previous!='CREATED':
        raise ApiError('Платёж уже передан в обработку; отмена недоступна.','CANCEL_NOT_ALLOWED',409)
    if status not in ('PENDING','SUCCESS','DECLINED','CANCELED') or (previous=='CREATED' and status=='SUCCESS'):
        raise ApiError('Недопустимый переход состояния.','CONFLICT',409)
    if payment.qr_expires_at and payment.qr_expires_at<=utcnow():
        status='DECLINED';payment.failure_reason='QR_EXPIRED'
    if status in ('PENDING','SUCCESS'):
        qr=await db.scalar(select(QrLink).where(QrLink.qr_id==payment.qr_id).with_for_update())
        merchant=await db.scalar(select(Merchant).where(Merchant.merchant_id==payment.merchant_id).with_for_update())
        employee=await db.scalar(select(Employee).where(Employee.employee_id==payment.employee_id).with_for_update())
        reason=None
        if not merchant or merchant.status.upper()!='ACTIVE':reason='MERCHANT_BLOCKED'
        elif not employee or not employee.active or employee.position!='worker' or employee.merchant_id!=payment.merchant_id:reason='INVALID_EMPLOYEE'
        elif not qr or qr.used_at or not qr.active:reason='QR_USED'
        elif qr.token_version!='v3' or qr.nonce!=payment.qr_nonce or qr.employee_id!=payment.employee_id or qr.merchant_id!=payment.merchant_id:reason='INVALID_QR'
        elif not hmac.compare_digest(qr.signature,sign_model_qr(qr)):reason='INVALID_QR'
        elif not qr.expires_at or qr.expires_at<=utcnow() or int(qr.exp)<=utcnow().timestamp():reason='QR_EXPIRED'
        if reason:status='DECLINED';payment.failure_reason=reason
        elif status=='SUCCESS':qr.used_at=utcnow();qr.active=False
    if status=='DECLINED' and not payment.failure_reason:payment.failure_reason='CARD_DECLINED'
    payment.status=status;payment.updated_at=utcnow()
    if status=='SUCCESS' and payment.goal_id:
        await db.execute(update(Goal).where(Goal.goal_id==payment.goal_id,Goal.employee_id==payment.employee_id,Goal.currency==payment.currency).values(raised=Goal.raised+payment.tip))
    action={'PENDING':'payment_confirmed','SUCCESS':'payment_succeeded','DECLINED':'payment_declined','CANCELED':'payment_canceled'}[status]
    record(db,payment,action,previous,actor)
    await db.flush()
    return payment

async def reconcile(db,payment):
    if payment.status in ('CREATED','PENDING') and payment.qr_expires_at and payment.qr_expires_at<=utcnow():
        return await transition(db,payment,'DECLINED')
    if payment.status=='PENDING':
        status=await PROVIDERS[payment.provider].status(payment.external_id,payment.provider_outcome,payment.provider_due_at)
        await transition(db,payment,status)
    return payment

async def confirm_payment(db,payment):
    await reconcile(db,payment)
    if payment.status!='CREATED':return payment
    if payment.provider_outcome=='cancelled':return await transition(db,payment,'CANCELED','client')
    await transition(db,payment,'PENDING','client')
    if payment.status=='PENDING':
        intent=await PROVIDERS[payment.provider].create(CheckoutRequest(payment.amount+payment.tip,payment.currency,payment.idempotency_key,payment.provider_outcome))
        payment.external_id=intent.external_id;payment.provider_due_at=intent.due_at
    await db.flush()
    return payment

async def create_payment(db,token,body,idempotency_key):
    if not idempotency_key or len(idempotency_key)>120 or len(idempotency_key)<8:
        raise ApiError('Нужен Idempotency-Key длиной от 8 до 120 символов.')
    await advisory_lock(db,'payment:'+idempotency_key)
    nonce,exp,signature=parse_qr_token(token)
    existing=await db.scalar(select(Payment).where(Payment.idempotency_key==idempotency_key).with_for_update())
    if existing:
        qr=await db.get(QrLink,existing.qr_id)
        if not qr or qr.nonce!=nonce or qr.exp!=exp or not hmac.compare_digest(qr.signature,signature) or not hmac.compare_digest(sign_model_qr(qr),signature):
            raise ApiError('Этот Idempotency-Key уже использован с другими данными.','CONFLICT',409)
        merchant=None
    else:qr,merchant=await resolve_qr(db,token,lock=True)
    if body.receipt_id!=qr.receipt_id:
        raise ApiError('Чек не соответствует QR-коду.','RECEIPT_MISMATCH',422)
    if body.currency!=qr.currency:raise ApiError('Валюта не совпадает с валютой QR-кода.')
    e=await db.get(Employee,body.employee_id)
    if not e or not e.active or e.position!='worker' or e.merchant_id!=qr.merchant_id or e.employee_id!=qr.employee_id:
        raise ApiError('Сотрудник не соответствует QR-коду.','INVALID_EMPLOYEE',422)
    bill=money(qr.bill_amount,qr.currency,maximum=1000000)
    amount=percent_tip(bill,body.percent,qr.currency) if body.percent is not None else money(body.amount,qr.currency,minimum=Decimal(0))
    if amount>bill*Decimal('.5'):raise ApiError('Чаевые не могут превышать 50% суммы чека.','TIP_OUT_OF_RANGE',422)
    if bill+amount>2000000:raise ApiError('Превышена максимальная сумма платежа.','AMOUNT_OUT_OF_RANGE',422)
    payload={'qr':qr.qr_id,'receipt':body.receipt_id,'employee':e.employee_id,'tip':str(amount),'currency':qr.currency,'scenario':body.scenario,'method':body.method}
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    if existing:
        if existing.request_fingerprint!=fingerprint:raise ApiError('Этот Idempotency-Key уже использован с другими данными.','CONFLICT',409)
        return existing,False
    pending=await db.scalar(select(Payment.payment_id).where(Payment.qr_id==qr.qr_id,Payment.status.in_(['CREATED','PENDING'])).limit(1))
    if pending:raise ApiError('По этому QR уже выполняется платёж. Дождитесь его завершения.','QR_PAYMENT_PENDING',409)
    goal=await db.scalar(select(Goal).where(Goal.employee_id==e.employee_id,Goal.active.is_(True),Goal.currency==qr.currency))
    now=utcnow()
    payment=Payment(merchant_id=merchant.merchant_id,employee_id=e.employee_id,amount=bill,tip=amount,status='CREATED',timestamp=now.isoformat(),currency=qr.currency,qr_id=qr.qr_id,qr_nonce=nonce,qr_expires_at=datetime.fromtimestamp(int(exp),timezone.utc),goal_id=goal.goal_id if goal else None,public_token=secrets.token_urlsafe(32),idempotency_key=idempotency_key,request_fingerprint=fingerprint,provider=body.method,provider_outcome=body.scenario,created_at=now,updated_at=now)
    db.add(payment);await db.flush();record(db,payment,'payment_created',None,'client');return payment,True

async def public_payment(db,token):
    p=await db.scalar(select(Payment).where(Payment.public_token==token).with_for_update())
    if not p:raise ApiError('Платёж не найден.','NOT_FOUND',404)
    return p
