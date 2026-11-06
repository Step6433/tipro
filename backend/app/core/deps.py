from typing import Annotated
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import get_settings
from app.core.errors import ApiError
from app.core.security import decode_token, role_of
from app.models import Employee, AuthSession, Merchant, utcnow

Db = Annotated[AsyncSession, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)

async def get_current_user(request: Request, db: Db, auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    token = auth.credentials if auth else request.cookies.get(get_settings().cookie_name)
    if not token:
        raise ApiError('Войдите в аккаунт.', 'UNAUTHORIZED', 401)
    claims = decode_token(token, 'access')
    try:
        user_id = int(claims['sub'])
    except (ValueError, TypeError):
        raise ApiError('Некорректная сессия.', 'UNAUTHORIZED', 401)
    session = await db.get(AuthSession, claims.get('jti', ''))
    user = await db.get(Employee, user_id)
    if not session or session.revoked or session.expires_at <= utcnow() or session.employee_id != user_id or not user or not user.active or role_of(user) == 'visitor':
        raise ApiError('Сессия завершена или аккаунт отключён.', 'UNAUTHORIZED', 401)
    if user.merchant_id and not user.platform_admin and request.url.path != '/api/auth/logout':
        merchant = await db.get(Merchant, user.merchant_id)
        if not merchant or merchant.status.upper() == 'BLOCKED':
            raise ApiError('Ресторан заблокирован.', 'MERCHANT_BLOCKED', 403)
        if merchant.status.upper() != 'ACTIVE':
            pending_status_access = (merchant.status.upper() == 'PENDING' and role_of(user) == 'merchant'
                                     and request.url.path in ('/api/auth/me', '/api/auth/logout'))
            if not pending_status_access:
                raise ApiError('Ресторан ожидает подтверждения администратора платформы.', 'MERCHANT_PENDING', 403)
    request.state.auth_session = session
    return user

User = Annotated[Employee, Depends(get_current_user)]

def require_role(user, *roles):
    if role_of(user) not in roles:
        raise ApiError('Недостаточно прав.', 'UNAUTHORIZED', 403)

def require_merchant(user, merchant_id):
    require_role(user, 'merchant')
    if user.merchant_id != merchant_id:
        raise ApiError('Нет доступа к этому ресторану.', 'UNAUTHORIZED', 403)
