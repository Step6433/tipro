from datetime import datetime, time, timedelta, date
from sqlalchemy import func, literal, DateTime
from app.core.errors import ApiError
from app.core.security import role_of
from app.models import Payment, Employee, Merchant
from app.core.money import CURRENCIES

def employee_conditions(user, merchant_id=None):
    role = role_of(user)
    conditions = [Employee.position == 'worker', Employee.platform_admin.is_(False)]
    if role == 'employee':
        conditions.append(Employee.employee_id == user.employee_id)
    elif role == 'merchant':
        conditions.append(Employee.merchant_id == user.merchant_id)
    if merchant_id:
        if role != 'admin' and merchant_id != user.merchant_id:
            raise ApiError('Нет доступа к другому ресторану.', 'UNAUTHORIZED', 403)
        conditions.append(Employee.merchant_id == merchant_id)
    return conditions

def payment_conditions(user, currency=None, start: date | None = None, end: date | None = None, employee_id=None, merchant_id=None, status=None, time_zone='UTC'):
    role = role_of(user); conditions = []
    if role == 'employee':
        if employee_id and employee_id != user.employee_id:
            raise ApiError('Нет доступа к чужим платежам.', 'UNAUTHORIZED', 403)
        conditions += [Payment.employee_id == user.employee_id, Payment.merchant_id == user.merchant_id]
    elif role == 'merchant':
        conditions.append(Payment.merchant_id == user.merchant_id)
    if merchant_id:
        if role != 'admin' and merchant_id != user.merchant_id:
            raise ApiError('Нет доступа к другому ресторану.', 'UNAUTHORIZED', 403)
        conditions.append(Payment.merchant_id == merchant_id)
    if employee_id:
        conditions.append(Payment.employee_id == employee_id)
    if currency:
        if currency not in CURRENCIES: raise ApiError('Неподдерживаемая валюта.')
        conditions.append(Payment.currency == currency)
    if start and end and start > end: raise ApiError('Начало периода должно быть не позже конца.')
    if start: conditions.append(Payment.created_at >= func.timezone(time_zone, literal(datetime.combine(start, time.min), type_=DateTime(timezone=False))))
    if end: conditions.append(Payment.created_at < func.timezone(time_zone, literal(datetime.combine(end + timedelta(days=1), time.min), type_=DateTime(timezone=False))))
    if status:
        statuses = {'success':'SUCCESS','declined':'DECLINED','cancelled':'CANCELED','pending':'PENDING'}
        if status not in statuses: raise ApiError('Неизвестный статус.')
        conditions.append(Payment.status == statuses[status])
    return conditions
