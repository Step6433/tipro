from fastapi import APIRouter, Query
from sqlalchemy import select, func
from app.core.deps import Db, User, require_role
from app.core.errors import ApiError
from app.models import Merchant, AuditEvent, utcnow
from app.core.security import role_of
from app.services.views import merchant_view

router = APIRouter(prefix='/admin', tags=['Platform administration'])

@router.get('/notifications')
async def notifications(db: Db, user: User, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
    require_role(user, 'admin')
    pending = func.upper(Merchant.status) == 'PENDING'
    total = await db.scalar(select(func.count()).select_from(Merchant).where(pending))
    merchants = await db.scalars(select(Merchant).where(pending).order_by(Merchant.created_at, Merchant.merchant_id).offset(offset).limit(limit))
    # Registration and its notification are the same persisted PENDING record, so they cannot diverge.
    items = [{'id': f'restaurant:{m.merchant_id}', 'type': 'restaurant_registration', 'restaurant': merchant_view(m)} for m in merchants]
    return {'items': items, 'total': total, 'offset': offset, 'limit': limit}

@router.post('/restaurants/{merchant_id}/approve')
async def approve(merchant_id: int, db: Db, user: User):
    require_role(user, 'admin')
    merchant = await db.scalar(select(Merchant).where(Merchant.merchant_id == merchant_id).with_for_update())
    if not merchant:
        raise ApiError('Ресторан не найден.', 'NOT_FOUND', 404)
    if merchant.status.upper() == 'ACTIVE':
        return merchant_view(merchant)
    if merchant.status.upper() != 'PENDING':
        raise ApiError('Можно подтвердить только ресторан, ожидающий проверки.', 'CONFLICT', 409)
    db.add(AuditEvent(merchant_id=merchant_id,action='merchant_approved',from_status='PENDING',to_status='ACTIVE',actor=f'admin:{user.employee_id}'))
    merchant.status = 'ACTIVE'
    merchant.approved_at = utcnow()
    merchant.approved_by = user.employee_id
    await db.flush()
    result = merchant_view(merchant)
    await db.commit()
    return result

@router.post('/restaurants/{merchant_id}/block')
async def block(merchant_id: int,db: Db,user: User):
    require_role(user,'admin')
    merchant=await db.scalar(select(Merchant).where(Merchant.merchant_id==merchant_id).with_for_update())
    if not merchant:raise ApiError('Ресторан не найден.','NOT_FOUND',404)
    if merchant.status!='BLOCKED':
        previous=merchant.status;merchant.status='BLOCKED'
        db.add(AuditEvent(merchant_id=merchant_id,action='merchant_blocked',from_status=previous,to_status='BLOCKED',actor=f'admin:{user.employee_id}'))
    await db.commit();return merchant_view(merchant)

@router.post('/restaurants/{merchant_id}/unblock')
async def unblock(merchant_id: int,db: Db,user: User):
    require_role(user,'admin')
    merchant=await db.scalar(select(Merchant).where(Merchant.merchant_id==merchant_id).with_for_update())
    if not merchant:raise ApiError('Ресторан не найден.','NOT_FOUND',404)
    if merchant.status=='BLOCKED':
        merchant.status='ACTIVE' if merchant.approved_at else 'PENDING'
        db.add(AuditEvent(merchant_id=merchant_id,action='merchant_unblocked',from_status='BLOCKED',to_status=merchant.status,actor=f'admin:{user.employee_id}'))
    await db.commit();return merchant_view(merchant)

@router.get('/audit')
async def audit(db: Db,user: User,payment_id: int|None=None,offset: int=Query(0,ge=0),limit: int=Query(100,ge=1,le=100)):
    require_role(user,'admin','merchant')
    conditions=[] if role_of(user)=='admin' else [AuditEvent.merchant_id==user.merchant_id]
    if payment_id is not None:conditions.append(AuditEvent.payment_id==payment_id)
    total=await db.scalar(select(func.count()).select_from(AuditEvent).where(*conditions))
    rows=await db.scalars(select(AuditEvent).where(*conditions).order_by(AuditEvent.event_id.desc()).offset(offset).limit(limit))
    return {'items':[{'id':str(e.event_id),'paymentId':str(e.payment_id) if e.payment_id else None,'qrId':str(e.qr_id) if e.qr_id else None,'merchantId':str(e.merchant_id),'action':e.action,'fromStatus':e.from_status,'toStatus':e.to_status,'amountTotal':str(e.amount_total) if e.amount_total is not None else None,'actor':e.actor,'at':e.at} for e in rows],'total':total,'offset':offset,'limit':limit}
