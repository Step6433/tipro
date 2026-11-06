from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Query
from sqlalchemy import select, func
from app.core.deps import Db, User, require_role
from app.core.dates import validate_timezone
from app.core.money import CURRENCIES
from app.core.errors import ApiError
from app.models import Payment, Merchant, Employee
from app.services.scopes import payment_conditions

router=APIRouter(tags=['Analytics'])

async def aggregate(db,user,currency=None,start=None,end=None,bucket='day',employee_id=None,merchant_id=None,time_zone='UTC'):
    if bucket not in ['day','week','month']:raise ApiError('Интервал должен быть day, week или month.')
    await validate_timezone(db,time_zone)
    conditions=payment_conditions(user,currency,start,end,employee_id,merchant_id,time_zone=time_zone)
    success=Payment.status=='SUCCESS'
    totals_stmt=select(Payment.currency,func.count().label('count'),func.count().filter(success).label('successful'),func.count().filter(Payment.status=='DECLINED').label('failed'),func.count().filter(Payment.status=='CANCELED').label('cancelled'),func.count().filter(Payment.status=='PENDING').label('pending'),func.coalesce(func.sum(Payment.tip).filter(success),0).label('total'),func.coalesce(func.avg(Payment.tip/func.nullif(Payment.amount,0)*100).filter(success),0).label('avg_tip_pct')).where(*conditions).group_by(Payment.currency)
    totals=[]
    for r in (await db.execute(totals_stmt)).mappings():
        average=(r['total']/r['successful']).quantize(Decimal(1).scaleb(-CURRENCIES.get(r['currency'],2))) if r['successful'] else Decimal(0)
        totals.append({**{k:v for k,v in r.items() if k!='avg_tip_pct'},'total':str(r['total']),'average':str(average),'avgTipPct':str(round(r['avg_tip_pct'],2)),'successRate':str(Decimal(r['successful'])/r['count']) if r['count'] else '0'})
    if currency and not totals:totals=[{'currency':currency,'count':0,'successful':0,'failed':0,'cancelled':0,'pending':0,'total':'0','average':'0','avgTipPct':'0','successRate':'0'}]
    period=func.date_trunc(bucket,func.timezone(time_zone,Payment.created_at))
    series_stmt=select(period.label('period'),Payment.currency,func.sum(Payment.tip).label('total'),func.count().label('count'),func.coalesce(func.avg(Payment.tip/func.nullif(Payment.amount,0)*100),0).label('avg_tip_pct')).where(*conditions,success,Payment.created_at.is_not(None)).group_by(period,Payment.currency).order_by(period)
    series=[{'period':r.period.date().isoformat(), 'date':r.period.date().isoformat(),'currency':r.currency,'total':str(r.total),'count':r._mapping['count'],'avgTipPct':str(round(r.avg_tip_pct,2))} for r in (await db.execute(series_stmt)).all()]
    employee_stmt=select(Payment.employee_id,Payment.currency,func.sum(Payment.tip).label('total'),func.count().label('count')).where(*conditions,success).group_by(Payment.employee_id,Payment.currency)
    by_employee=[{'employeeId':str(r.employee_id),'currency':r.currency,'total':str(r.total),'count':r._mapping['count']} for r in (await db.execute(employee_stmt)).all()]
    day=func.date_trunc('day',func.timezone(time_zone,Payment.created_at))
    daily=(await db.execute(select(day.label('day'),Payment.currency,func.sum(Payment.tip).label('total')).where(*conditions,success,Payment.created_at.is_not(None)).group_by(day,Payment.currency).order_by(func.sum(Payment.tip).desc(),day))).all()
    for total in totals:
        best=next((r for r in daily if r.currency==total['currency']),None)
        total['topDay']=best.day.date().isoformat() if best else None
    return {'totals':totals,'series':series,'byEmployee':by_employee,'bucket':bucket,'timezone':time_zone}

@router.get('/analytics')
async def analytics(db: Db,user: User,currency: str|None=None,start: date|None=None,end: date|None=None,bucket: str='day',employee_id: int|None=None,merchant_id: int|None=None,timezone: str=Query('UTC',min_length=1,max_length=100)):
    return await aggregate(db,user,currency,start,end,bucket,employee_id,merchant_id,time_zone=timezone)

@router.get('/admin/overview')
async def admin(db: Db,user: User,currency: str|None=None,timezone: str=Query('UTC',min_length=1,max_length=100)):
    require_role(user,'admin')
    return {'restaurantCount':await db.scalar(select(func.count()).select_from(Merchant)),'employeeCount':await db.scalar(select(func.count()).select_from(Employee).where(Employee.position=='worker')),'analytics':await aggregate(db,user,currency,time_zone=timezone)}
