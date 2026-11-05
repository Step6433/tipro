import hashlib
import hmac
import secrets
from datetime import timedelta
import jwt
from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool
from app.config import get_settings
from app.core.errors import ApiError
from app.models import Employee, AuthSession, utcnow

passwords = PasswordHash.recommended()
ROLE_MAP = {'manager': 'merchant', 'worker': 'employee'}

def role_of(user: Employee):
    return 'admin' if user.platform_admin else ROLE_MAP.get(user.position, 'visitor')

def session_view(user):
    role = role_of(user)
    return {'userId': str(user.employee_id), 'role': role, 'merchantId': str(user.merchant_id) if user.merchant_id else None, 'employeeId': str(user.employee_id) if role == 'employee' else None}

def user_view(user):
    return {'id': str(user.employee_id), 'name': user.name, 'email': user.auth_email, **session_view(user)}

def encode_token(payload):
    return jwt.encode({'iss': 'tipro', **payload}, get_settings().jwt_secret.get_secret_value(), algorithm='HS256')

def decode_token(token, kind):
    try:
        claims = jwt.decode(token, get_settings().jwt_secret.get_secret_value(), algorithms=['HS256'], issuer='tipro', options={'require': ['exp', 'sub', 'kind']})
        if claims['kind'] != kind:
            raise ValueError
        return claims
    except (jwt.PyJWTError, ValueError, TypeError):
        raise ApiError('Токен недействителен или просрочен.', 'INVALID_ACCESS' if kind == 'invite' else 'UNAUTHORIZED', 401)

async def hash_password(value):
    return await run_in_threadpool(passwords.hash, value)

async def verify_password(value, hashed):
    try:
        return await run_in_threadpool(passwords.verify, value, hashed)
    except Exception:
        return False

async def issue_session(db, user):
    expires = utcnow() + timedelta(minutes=get_settings().access_token_minutes)
    session = AuthSession(session_id=secrets.token_urlsafe(32), employee_id=user.employee_id, expires_at=expires, revoked=False)
    db.add(session)
    token = encode_token({'sub': str(user.employee_id), 'jti': session.session_id, 'kind': 'access', 'exp': expires, 'iat': utcnow()})
    return {'accessToken': token, 'tokenType': 'bearer', 'session': session_view(user), 'user': user_view(user)}

def invite_token(user):
    if not user.invite_nonce or user.invite_consumed_at or not user.invite_expires_at or user.invite_expires_at <= utcnow() or user.auth_email:
        return None
    return encode_token({'kind': 'invite', 'sub': str(user.employee_id), 'nonce': user.invite_nonce, 'exp': user.invite_expires_at})

def sign_qr(nonce, exp):
    """Authenticate an unambiguous nonce + expiry payload with the server secret."""
    payload = f'qr:{nonce}:{exp}'.encode()
    return hmac.new(get_settings().jwt_secret.get_secret_value().encode(), payload, hashlib.sha256).hexdigest()

def qr_token(q):
    return f'{q.nonce}.{q.exp}.{q.signature}' if q.token_version in ('v1', 'v2') else q.nonce

def parse_qr_token(token):
    try:
        nonce, exp, signature = token.split('.')
        if not (1 <= len(nonce) <= 100 and nonce.isascii() and all(c.isalnum() or c in '_-' for c in nonce)):
            raise ValueError
        if not (exp.isascii() and exp.isdigit() and len(exp) <= 12 and str(int(exp)) == exp):
            raise ValueError
        if not hmac.compare_digest(signature, sign_qr(nonce, exp)):
            raise ValueError
        return nonce, exp, signature
    except (ValueError, TypeError):
        raise ApiError('Подпись QR-кода недействительна.', 'INVALID_QR', 404)
