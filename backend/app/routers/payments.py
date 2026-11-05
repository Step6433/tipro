import csv
import hashlib
import hmac
import io
import time
from datetime import date
from fastapi import APIRouter, Header, Request, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from app.config import get_settings
from app.core.dates import validate_timezone
from app.core.deps import Db, User
from app.core.errors import ApiError
from app.models import Payment, Employee, WebhookEvent
from app.schemas.requests import PaymentInput, WebhookInput
from app.services.payments import create_payment, public_payment, reconcile, transition, advisory_lock
from app.services.scopes import payment_conditions
from app.services.views import payment_view, STATUS

router=APIRouter(tags=['Payments'])

@router.post('/public/qrs/{token}/payments')
async def create(token: str,body: PaymentInput,db: Db,response: Response,idempotency_key: str|None=Header(default=None,alias='Idempotency-Key')):
    payment,created=await create_payment(db,token,body,idempotency_key)
    result=payment_view(payment,True);await db.commit();response.status_code=201 if created else 200
    return result

@router.get('/public/payments/{token}')
async def status(token: str,db: Db):
    p=await public_payment(db,token);await reconcile(db,p);result=payment_view(p,True);await db.commit();return result

@router.post('/public/payments/{token}/cancel')
async def cancel(token: str,db: Db):
    p=await public_payment(db,token);await reconcile(db,p)
    if p.status=='PENDING':await transition(db,p,'CANCELED')
    result=payment_view(p,True);await db.commit();return result

@router.get('/payments')
async def history(db: Db,user: User,currency: str|None=None,start: date|None=None,end: date|None=None,employee_id: int|None=None,merchant_id: int|None=None,status: str|None=None,offset: int=Query(0,ge=0),limit: int=Query(100,ge=1,le=100),timezone: str=Query('UTC',min_length=1,max_length=100)):
    await validate_timezone(db,timezone)
    conditions=payment_conditions(user,currency,start,end,employee_id,merchant_id,status,time_zone=timezone)
    total=await db.scalar(select(func.count()).select_from(Payment).where(*conditions))
    rows=await db.scalars(select(Payment).where(*conditions).order_by(Payment.created_at.desc().nulls_last(),Payment.payment_id.desc()).offset(offset).limit(limit))
    return {'items':[payment_view(p) for p in rows],'total':total,'offset':offset,'limit':limit}

@router.get('/payments/export')
async def export(db: Db,user: User,currency: str|None=None,start: date|None=None,end: date|None=None,employee_id: int|None=None,merchant_id: int|None=None,status: str|None=None,timezone: str=Query('UTC',min_length=1,max_length=100)):
    await validate_timezone(db,timezone)
    conditions=payment_conditions(user,currency,start,end,employee_id,merchant_id,status,time_zone=timezone)
    stmt=select(Payment,Employee.name).join(Employee,Payment.employee_id==Employee.employee_id).where(*conditions).order_by(Payment.created_at.desc().nulls_last())
    def row(values):
        def safe(value):
            value=str(value)
            return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value
        buffer=io.StringIO();csv.writer(buffer,delimiter=';').writerow([safe(v) for v in values]);return buffer.getvalue()
    async def generate():
        yield '\ufeff'+row(['ID','Дата UTC','Сотрудник','Чаевые','Валюта','Статус'])
        result=await db.stream(stmt.execution_options(yield_per=200))
        async for payment,name in result:
            yield row([payment.payment_id,payment.created_at.isoformat() if payment.created_at else '',name,payment.tip,payment.currency,STATUS[payment.status]])
    return StreamingResponse(generate(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="tipro-payments.csv"'})

@router.post('/webhooks/demo')
async def webhook(request: Request,db: Db,x_webhook_timestamp: str=Header(),x_webhook_signature: str=Header()):
    raw=await request.body()
    try:timestamp=int(x_webhook_timestamp)
    except ValueError:raise ApiError('Некорректная подпись.','INVALID_SIGNATURE',401)
    if abs(time.time()-timestamp)>300:raise ApiError('Подпись просрочена.','INVALID_SIGNATURE',401)
    expected=hmac.new(get_settings().webhook_secret.get_secret_value().encode(),x_webhook_timestamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,x_webhook_signature):raise ApiError('Некорректная подпись.','INVALID_SIGNATURE',401)
    body=WebhookInput.model_validate_json(raw)
    digest=hashlib.sha256(raw).hexdigest()
    await advisory_lock(db,'webhook:'+body.event_id)
    previous=await db.get(WebhookEvent,body.event_id)
    if previous:
        if previous.digest!=digest:raise ApiError('Идентификатор события уже использован.','CONFLICT',409)
        return {'ok':True,'duplicate':True}
    payment=await db.scalar(select(Payment).where(Payment.external_id==body.external_id,Payment.provider=='demo').with_for_update())
    if not payment:raise ApiError('Платёж не найден.','NOT_FOUND',404)
    if payment.tip!=body.amount or payment.currency!=body.currency:raise ApiError('Сумма или валюта подтверждения не совпадает.')
    await transition(db,payment,{'success':'SUCCESS','failed':'DECLINED','cancelled':'CANCELED'}[body.status])
    db.add(WebhookEvent(event_id=body.event_id,digest=digest,payment_id=payment.payment_id));await db.commit()
    return {'ok':True,'duplicate':False,'status':STATUS[payment.status],'errorCode':payment.failure_reason}
