import hmac
from fastapi import APIRouter, Response, Request
from sqlalchemy import select
from app.config import get_settings
from app.core.deps import Db, User
from app.core.errors import ApiError
from app.core.security import hash_password, verify_password, issue_session, session_view, user_view, role_of, decode_token, passwords
from app.models import Employee, Merchant, utcnow
from app.schemas.requests import Login, Register

router = APIRouter(prefix='/auth', tags=['Authentication'])
DUMMY_HASH = passwords.hash('invalid-account-comparison-only')

def set_cookie(response, token):
    settings = get_settings()
    response.set_cookie(settings.cookie_name, token, httponly=True, secure=settings.cookie_secure, samesite='lax', path='/api', max_age=settings.access_token_minutes * 60)

async def invited_employee(db, token, lock=False):
    claims = decode_token(token or '', 'invite')
    try:
        employee_id = int(claims['sub'])
    except (ValueError, TypeError):
        raise ApiError('Приглашение недействительно.', 'INVALID_ACCESS', 400)
    stmt = select(Employee).where(Employee.employee_id == employee_id)
    e = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not e or e.position != 'worker' or not e.active or e.auth_email or e.invite_consumed_at or not e.invite_nonce or not hmac.compare_digest(e.invite_nonce, str(claims.get('nonce', ''))) or not e.invite_expires_at or e.invite_expires_at <= utcnow():
        raise ApiError('Приглашение недействительно или уже использовано.', 'INVALID_ACCESS', 400)
    m = await db.get(Merchant, e.merchant_id)
    if not m or m.status.upper() != 'ACTIVE':
        raise ApiError('Ресторан недоступен.', 'INVALID_ACCESS', 400)
    return e, m

@router.post('/register', status_code=201)
async def register(body: Register, response: Response, db: Db):
    email = str(body.email).lower()
    if body.role == 'admin' and not get_settings().allow_admin_registration:
        raise ApiError('Администратора платформы создают через серверную команду create-admin.', 'UNAUTHORIZED', 403)
    if await db.scalar(select(Employee.employee_id).where(Employee.auth_email == email)):
        raise ApiError('Аккаунт с таким email уже существует.', 'CONFLICT', 409)
    hashed = await hash_password(body.password)
    if body.role == 'employee':
        user, _ = await invited_employee(db, body.invite, lock=True)
        user.auth_email = email; user.login = email; user.password_hash = hashed; user.password = None; user.invite_consumed_at = utcnow()
    else:
        merchant = None
        if body.role == 'merchant':
            if not body.restaurant_name:
                raise ApiError('Укажите название ресторана.')
            merchant = Merchant(name=body.restaurant_name, status='PENDING', contact_email=email)
            db.add(merchant); await db.flush()
        user = Employee(name=body.name, merchant_id=merchant.merchant_id if merchant else None, position='manager', platform_admin=body.role == 'admin', title='Администратор', login=email, auth_email=email, password_hash=hashed, active=True, payment_details='')
        db.add(user); await db.flush()
    result = await issue_session(db, user)
    result['session'].update(await approval_details(db, user))
    await db.commit(); set_cookie(response, result['accessToken'])
    return result

@router.post('/login')
async def login(body: Login, response: Response, db: Db):
    user = await db.scalar(select(Employee).where(Employee.auth_email == body.email.lower()))
    valid = await verify_password(body.password, user.password_hash if user and user.password_hash else DUMMY_HASH)
    if not valid or not user or not user.active or role_of(user) == 'visitor':
        raise ApiError('Неверный email, пароль или аккаунт отключён.', 'UNAUTHORIZED', 401)
    if user.merchant_id and not user.platform_admin:
        m = await db.get(Merchant, user.merchant_id)
        if not m or (m.status.upper() != 'ACTIVE' and not (m.status.upper() == 'PENDING' and role_of(user) == 'merchant')):
            raise ApiError('Ресторан недоступен.', 'MERCHANT_BLOCKED' if m and m.status.upper()=='BLOCKED' else 'UNAUTHORIZED', 403)
    result = await issue_session(db, user)
    result['session'].update(await approval_details(db, user))
    await db.commit(); set_cookie(response, result['accessToken'])
    return result

async def approval_details(db, user):
    merchant = await db.get(Merchant, user.merchant_id) if user.merchant_id else None
    return {'merchantStatus': merchant.status.upper() if merchant else None, 'merchantName': merchant.name if merchant else None}

@router.get('/me')
async def me(user: User, db: Db):
    return {'session': {**session_view(user), **await approval_details(db, user)}, 'user': user_view(user)}

@router.post('/logout', status_code=204)
async def logout(request: Request, response: Response, user: User, db: Db):
    request.state.auth_session.revoked = True
    await db.commit(); response.delete_cookie(get_settings().cookie_name, path='/api', secure=get_settings().cookie_secure, httponly=True, samesite='lax')

@router.get('/invitations/{token}')
async def invitation(token: str, db: Db):
    e, m = await invited_employee(db, token)
    return {'name': e.name, 'position': e.title, 'restaurantName': m.name}
