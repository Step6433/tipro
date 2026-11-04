import secrets
from datetime import timedelta
from fastapi import APIRouter, Query
from sqlalchemy import select, func, update
from app.core.deps import Db, User, require_role, require_merchant
from app.core.errors import ApiError
from app.core.security import role_of, user_view, invite_token
from app.core.money import CURRENCIES, money
from app.models import Merchant, Employee, Goal, utcnow
from app.schemas.requests import EmployeeInput, GoalInput, SettingsInput
from app.services.views import merchant_view, employee_view
from app.services.scopes import employee_conditions

router = APIRouter(tags=['Workspace'])

async def scoped_employee(db, user, employee_id, lock=False):
    stmt = select(Employee).where(Employee.employee_id == employee_id, *employee_conditions(user))
    e = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not e: raise ApiError('Нет доступа к сотруднику.', 'UNAUTHORIZED', 403)
    return e

async def employee_goals(db, employees):
    ids = [e.employee_id for e in employees]
    return list((await db.scalars(select(Goal).where(Goal.employee_id.in_(ids)).order_by(Goal.created_at))).all()) if ids else []

@router.get('/workspace')
async def workspace(db: Db, user: User):
    merchant = await db.get(Merchant, user.merchant_id) if user.merchant_id else None
    return {'user': user_view(user), 'merchant': merchant_view(merchant) if merchant else None}

@router.get('/employees')
async def employees(db: Db, user: User, merchant_id: int | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), active: bool | None = None):
    conditions = employee_conditions(user, merchant_id)
    if active is not None: conditions.append(Employee.active == active)
    total = await db.scalar(select(func.count()).select_from(Employee).where(*conditions))
    rows = list((await db.scalars(select(Employee).where(*conditions).order_by(Employee.employee_id).offset(offset).limit(limit))).all())
    goals = await employee_goals(db, rows)
    return {'items': [employee_view(e, goals, True, role_of(user) == 'merchant') for e in rows], 'total': total, 'offset': offset, 'limit': limit}

@router.get('/employees/{employee_id}')
async def employee(employee_id: int, db: Db, user: User):
    e = await scoped_employee(db, user, employee_id)
    return employee_view(e, await employee_goals(db, [e]), True, role_of(user) == 'merchant')

@router.post('/employees', status_code=201)
async def create_employee(body: EmployeeInput, db: Db, user: User):
    require_role(user, 'merchant')
    e = Employee(merchant_id=user.merchant_id, name=body.name, title=body.role, position='worker', active=body.active, invite_nonce=secrets.token_urlsafe(24), invite_expires_at=utcnow()+timedelta(days=7), payment_details='')
    db.add(e); await db.flush(); result = employee_view(e, [], True, True); await db.commit(); return result

@router.patch('/employees/{employee_id}')
async def edit_employee(employee_id: int, body: EmployeeInput, db: Db, user: User):
    require_role(user, 'merchant'); e = await scoped_employee(db, user, employee_id, lock=True)
    e.name=body.name; e.title=body.role; e.active=body.active
    result=employee_view(e, await employee_goals(db, [e]), True, True)
    await db.commit(); return result

@router.post('/employees/{employee_id}/invitation')
async def renew_invitation(employee_id: int, db: Db, user: User):
    require_role(user, 'merchant'); e=await scoped_employee(db,user,employee_id,lock=True)
    if e.auth_email or not e.active: raise ApiError('Аккаунт уже создан или сотрудник отключён.', 'CONFLICT', 409)
    e.invite_nonce=secrets.token_urlsafe(24);e.invite_expires_at=utcnow()+timedelta(days=7);e.invite_consumed_at=None
    await db.commit(); return employee_view(e, await employee_goals(db,[e]), True, True)

async def goal_owner(db, user, employee_id):
    require_role(user, 'employee')
    if user.employee_id != employee_id: raise ApiError('Можно изменять только свои цели.', 'UNAUTHORIZED', 403)
    return await scoped_employee(db, user, employee_id, lock=True)

@router.post('/employees/{employee_id}/goals', status_code=201)
async def create_goal(employee_id: int, body: GoalInput, db: Db, user: User):
    e=await goal_owner(db,user,employee_id); target=money(body.target,body.currency)
    await db.execute(update(Goal).where(Goal.employee_id==employee_id).values(active=False))
    g=Goal(employee_id=employee_id,title=body.title,target=target,currency=body.currency,raised=0,active=True)
    db.add(g);await db.flush(); result=employee_view(e,await employee_goals(db,[e]),True)
    await db.commit();return result

@router.patch('/employees/{employee_id}/goals/{goal_id}')
async def edit_goal(employee_id: int, goal_id: int, body: GoalInput, db: Db, user: User):
    e=await goal_owner(db,user,employee_id)
    g=await db.scalar(select(Goal).where(Goal.goal_id==goal_id,Goal.employee_id==employee_id).with_for_update())
    if not g: raise ApiError('Цель не найдена.','NOT_FOUND',404)
    if g.currency!=body.currency and g.raised: raise ApiError('У цели с накоплениями нельзя менять валюту.')
    g.target=money(body.target,body.currency);g.currency=body.currency;g.title=body.title
    await db.flush();result=employee_view(e,await employee_goals(db,[e]),True);await db.commit();return result

@router.put('/employees/{employee_id}/goals/{goal_id}/active')
async def activate_goal(employee_id: int,goal_id: int,db: Db,user: User):
    await goal_owner(db,user,employee_id)
    g=await db.scalar(select(Goal).where(Goal.goal_id==goal_id,Goal.employee_id==employee_id))
    if not g: raise ApiError('Цель не найдена.','NOT_FOUND',404)
    await db.execute(update(Goal).where(Goal.employee_id==employee_id).values(active=False))
    await db.execute(update(Goal).where(Goal.goal_id==goal_id).values(active=True));await db.commit()
    return {'ok':True}

@router.get('/restaurants')
async def restaurants(db: Db,user: User,offset: int=Query(0,ge=0),limit: int=Query(100,ge=1,le=100)):
    condition=[] if role_of(user)=='admin' else [Merchant.merchant_id==user.merchant_id]
    total=await db.scalar(select(func.count()).select_from(Merchant).where(*condition))
    rows=await db.scalars(select(Merchant).where(*condition).order_by(Merchant.merchant_id).offset(offset).limit(limit))
    return {'items':[merchant_view(m) for m in rows],'total':total,'offset':offset,'limit':limit}

@router.get('/restaurants/{merchant_id}')
async def restaurant(merchant_id: int,db: Db,user: User):
    if role_of(user)!='admin' and user.merchant_id!=merchant_id:raise ApiError('Нет доступа к ресторану.','UNAUTHORIZED',403)
    m=await db.get(Merchant,merchant_id)
    if not m:raise ApiError('Ресторан не найден.','NOT_FOUND',404)
    return merchant_view(m)

@router.patch('/restaurants/{merchant_id}/settings')
async def settings(merchant_id: int,body: SettingsInput,db: Db,user: User):
    require_merchant(user,merchant_id);m=await db.get(Merchant,merchant_id)
    values=body.model_dump(exclude_unset=True)
    if values.get('currency') is not None and values['currency'] not in CURRENCIES:raise ApiError('Неподдерживаемая валюта.')
    percentages=values.get('tip_percentages')
    if percentages is not None and (len(set(percentages))!=len(percentages) or any(p<1 or p>100 for p in percentages)):raise ApiError('Проценты должны быть уникальными числами от 1 до 100.')
    for field,value in values.items():
        if value is not None or field=='description':setattr(m,field,value)
    await db.commit();return merchant_view(m)
