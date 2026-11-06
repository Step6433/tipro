import io
import secrets
import hmac
from datetime import timedelta
from urllib.parse import urlencode
import qrcode
from fastapi import APIRouter, Query, Response
from sqlalchemy import select, func, text
from app.config import get_settings
from app.core.deps import Db, User, require_role, require_merchant
from app.core.errors import ApiError
from app.core.security import sign_model_qr, qr_token, parse_qr_token
from app.core.money import money
from app.models import QrLink, Merchant, Employee, Goal, utcnow
from app.schemas.requests import QrInput, QrUpdate
from app.services.views import qr_view, merchant_view, employee_view

router=APIRouter(tags=['QR links'])

async def resolve_qr(db, token, lock=False):
    nonce, exp, signature = parse_qr_token(token)
    stmt=select(QrLink).where(QrLink.nonce==nonce,QrLink.token_version=='v3')
    q=await db.scalar(stmt.with_for_update() if lock else stmt)
    if not q or q.exp!=exp or not hmac.compare_digest(q.signature,signature) or not hmac.compare_digest(sign_model_qr(q),signature):
        raise ApiError('QR-код недействителен.','INVALID_QR',422)
    if q.used_at:
        raise ApiError('QR-код уже использован. Попросите новый код.','QR_USED',409)
    if not q.expires_at or q.expires_at<=utcnow() or int(exp)<=utcnow().timestamp():
        raise ApiError('Срок действия QR-кода истёк. Попросите новый код.','QR_EXPIRED',410)
    if not q.active:
        raise ApiError('QR-код отключён.','INVALID_QR',422)
    m=await db.scalar(select(Merchant).where(Merchant.merchant_id==q.merchant_id).with_for_update()) if lock else await db.get(Merchant,q.merchant_id)
    if not m or m.status.upper()!='ACTIVE':
        raise ApiError('Ресторан заблокирован или не активирован.','MERCHANT_BLOCKED' if m and m.status.upper()=='BLOCKED' else 'MERCHANT_PENDING',403)
    e=await db.get(Employee,q.employee_id)
    if not e or not e.active or e.position!='worker' or e.merchant_id!=m.merchant_id:
        raise ApiError('Сотрудник недоступен. Создайте новый QR-код.','INVALID_EMPLOYEE',403)
    return q,m

def qr_url(q):
    return get_settings().frontend_url.rstrip('/')+f'/restaurant/{q.merchant_id}?'+urlencode({'qr':qr_token(q)})

@router.get('/qrs')
async def list_qrs(db: Db,user: User,offset: int=Query(0,ge=0),limit: int=Query(100,ge=1,le=100)):
    require_role(user,'merchant');where=QrLink.merchant_id==user.merchant_id
    total=await db.scalar(select(func.count()).select_from(QrLink).where(where))
    rows=await db.scalars(select(QrLink).where(where).order_by(QrLink.qr_id.desc()).offset(offset).limit(limit))
    return {'items':[{**qr_view(q),'url':qr_url(q)} for q in rows],'total':total,'offset':offset,'limit':limit}

@router.post('/qrs',status_code=201)
async def create_qr(body: QrInput,db: Db,user: User):
    require_role(user,'merchant');m=await db.get(Merchant,user.merchant_id)
    currency=body.currency or m.currency
    bill=money(body.bill_amount,currency,maximum=1000000)
    receipt_id=await db.scalar(text("SELECT nextval('receipt_id_seq')"))
    receipt_number=body.receipt_number or str(receipt_id)
    if await db.scalar(select(QrLink.qr_id).where(QrLink.merchant_id==m.merchant_id,QrLink.receipt_number==receipt_number,QrLink.token_version=='v3')):
        raise ApiError('Для этого чека QR уже существует.','RECEIPT_MISMATCH',409)
    if body.employee_id:
        e=await db.get(Employee,body.employee_id)
        if not e or e.merchant_id!=m.merchant_id or e.position!='worker' or not e.active:raise ApiError('Сотрудник не принадлежит ресторану.','INVALID_EMPLOYEE',400)
    token=str(secrets.randbits(256));created=utcnow().replace(microsecond=0);expires=created+timedelta(hours=24)
    exp=str(int(expires.timestamp()))
    q=QrLink(merchant_id=m.merchant_id,employee_id=body.employee_id,receipt_id=receipt_id,receipt_number=receipt_number,bill_amount=bill,currency=currency,nonce=token,exp=exp,signature='',expires_at=expires,active=True,token_version='v3',created_at=created,label=body.label or 'QR сотрудника')
    q.signature=sign_model_qr(q)
    db.add(q);await db.flush();result={**qr_view(q),'url':qr_url(q)};await db.commit();return result

@router.patch('/qrs/{token}')
async def update_qr(token: str,body: QrUpdate,db: Db,user: User):
    nonce, exp, signature = parse_qr_token(token)
    q=await db.scalar(select(QrLink).where(QrLink.nonce==nonce,QrLink.exp==exp,QrLink.signature==signature).with_for_update())
    if not q:raise ApiError('QR-код не найден.','NOT_FOUND',404)
    require_merchant(user,q.merchant_id)
    if q.token_version!='v3':raise ApiError('Создайте новый QR: старый формат не поддерживается.')
    if body.active and (q.used_at or not q.expires_at or q.expires_at<=utcnow()):
        raise ApiError('Использованный или просроченный QR нельзя включить повторно.','CONFLICT',409)
    q.active=body.active;await db.commit();return qr_view(q)

@router.get('/qrs/{token}/image')
async def qr_image(token: str,db: Db,user: User):
    nonce, exp, signature = parse_qr_token(token)
    q=await db.scalar(select(QrLink).where(QrLink.nonce==nonce,QrLink.exp==exp,QrLink.signature==signature).with_for_update())
    if not q:raise ApiError('QR-код не найден.','NOT_FOUND',404)
    require_merchant(user,q.merchant_id)
    if q.token_version!='v3' or not q.active or q.used_at or not q.expires_at or q.expires_at<=utcnow():
        raise ApiError('Этот QR больше не действует. Создайте новый код.','INVALID_QR',404)
    buffer=io.BytesIO();qrcode.make(qr_url(q)).save(buffer,format='PNG')
    return Response(buffer.getvalue(),media_type='image/png',headers={'Content-Disposition':f'attachment; filename="tipro-qr-{q.qr_id}.png"'})

async def public_qr(db,token,merchant_id=None):
    q,m=await resolve_qr(db,token)
    if merchant_id is not None and m.merchant_id!=merchant_id:raise ApiError('QR относится к другому ресторану.','INVALID_QR',422)
    conditions=[Employee.merchant_id==m.merchant_id,Employee.position=='worker',Employee.active.is_(True)]
    if q.employee_id:conditions.append(Employee.employee_id==q.employee_id)
    employees=list((await db.scalars(select(Employee).where(*conditions).order_by(Employee.name))).all())
    ids=[e.employee_id for e in employees]
    goals=list((await db.scalars(select(Goal).where(Goal.employee_id.in_(ids),Goal.active.is_(True)))).all()) if ids else []
    public_merchant=merchant_view(m);public_merchant.pop('email',None);public_merchant.pop('approvedBy',None);public_merchant.pop('approvedAt',None)
    return {'qr':qr_view(q),'merchant':public_merchant,'employees':[employee_view(e,goals) for e in employees],'demoControls':get_settings().allow_demo_controls}

@router.get('/public/qrs/{token}')
async def public_by_token(token: str,db: Db):return await public_qr(db,token)

@router.get('/public/restaurants/{merchant_id}')
async def public_restaurant(merchant_id: int,qr: str,db: Db):return await public_qr(db,qr,merchant_id)
