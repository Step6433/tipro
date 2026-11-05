from fastapi import APIRouter, Query
from sqlalchemy import select, func
from app.core.deps import Db, User, require_role
from app.core.errors import ApiError
from app.models import Merchant, utcnow
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
    merchant.status = 'ACTIVE'
    merchant.approved_at = utcnow()
    merchant.approved_by = user.employee_id
    await db.flush()
    result = merchant_view(merchant)
    await db.commit()
    return result
