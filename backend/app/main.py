import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.config import get_settings
from app.database import engine
from app.core.errors import ApiError
from app.routers import auth, workspace, qrs, payments, analytics, admin

settings=get_settings()
# Access paths can contain public QR / payment capabilities. Do not log them.
logging.getLogger('uvicorn.access').disabled=True

@asynccontextmanager
async def lifespan(app):
    from app.services.worker import demo_confirmation_loop
    worker=asyncio.create_task(demo_confirmation_loop())
    try:yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):await worker
        await engine.dispose()

app=FastAPI(title='Tipro API',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,allow_credentials=True,allow_methods=['GET','POST','PATCH','PUT','DELETE','OPTIONS'],allow_headers=['Authorization','Content-Type','Idempotency-Key','X-Webhook-Timestamp','X-Webhook-Signature'])

attempts=defaultdict(deque)
@app.middleware('http')
async def origin_and_limits(request: Request,call_next):
    if request.method in ['POST','PUT','PATCH','DELETE']:
        origin=request.headers.get('origin')
        if origin and origin not in settings.cors_origins:
            return JSONResponse({'message':'Недоверенный Origin.','code':'UNAUTHORIZED'},status_code=403)
    if request.url.path in ['/api/auth/login','/api/auth/register'] and request.method=='POST':
        now=time.monotonic();key=request.client.host if request.client else 'unknown'
        queue=attempts[key]
        while queue and queue[0]<now-300:queue.popleft()
        if len(queue)>=60:return JSONResponse({'message':'Слишком много попыток. Повторите позже.','code':'RATE_LIMIT'},status_code=429)
        queue.append(now)
        if len(attempts)>10000:
            for old_key in list(attempts):
                if not attempts[old_key] or attempts[old_key][-1]<now-300:attempts.pop(old_key,None)
    if request.url.path.startswith('/api/public/'):
        now=time.monotonic();key='public:'+(request.client.host if request.client else 'unknown')
        queue=attempts[key]
        while queue and queue[0]<now-60:queue.popleft()
        if len(queue)>=300:return JSONResponse({'message':'Слишком много запросов. Повторите позже.','code':'RATE_LIMIT','retryable':True},status_code=429)
        queue.append(now)
        if len(attempts)>10000:
            for old_key in list(attempts):
                if not attempts[old_key] or attempts[old_key][-1]<now-300:attempts.pop(old_key,None)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.exception_handler(ApiError)
async def api_error(request,exc):return JSONResponse({'message':exc.message,'code':exc.code,'retryable':exc.code in ('QR_EXPIRED','CARD_DECLINED','RATE_LIMIT')},status_code=exc.status)

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    # Never echo password fields or bearer/capability tokens from invalid input.
    fields=['.'.join(str(p) for p in e['loc']) for e in exc.errors()]
    return JSONResponse({'message':'Проверьте поля запроса: '+', '.join(fields),'code':'VALIDATION'},status_code=422)

@app.exception_handler(ValidationError)
async def schema_error(request,exc):return JSONResponse({'message':'Неверный формат данных.','code':'VALIDATION'},status_code=422)

@app.exception_handler(IntegrityError)
async def conflict(request,exc):return JSONResponse({'message':'Такая запись уже существует или нарушена связь данных.','code':'CONFLICT'},status_code=409)

@app.exception_handler(SQLAlchemyError)
async def database_error(request,exc):
    logging.getLogger('tipro').error('database_operation_failed')
    return JSONResponse({'message':'База данных недоступна или миграции не применены.','code':'DATABASE_ERROR'},status_code=503)

@app.get('/api/health',tags=['Health'])
async def health():
    async with engine.connect() as conn:await conn.execute(text('SELECT 1'))
    return {'status':'ok','database':'postgresql','provider':'demo'}

@app.get('/api/capabilities',tags=['Configuration'])
async def capabilities():
    from app.core.money import CURRENCIES
    return {'frontendUrl':settings.frontend_url.rstrip('/'),'currencies':CURRENCIES,'provider':'demo','paymentMethods':['demo'],'demoControls':settings.allow_demo_controls,'adminRegistration':settings.allow_admin_registration}

for router in [auth.router,workspace.router,qrs.router,payments.router,analytics.router,admin.router]:app.include_router(router,prefix='/api')
