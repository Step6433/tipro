"""Confirm an intentionally pending demo payment through the signed server webhook.
Usage: python scripts/send_demo_webhook.py PAYMENT_ID [--status success|failed|cancelled]
Run only as the backend operator. The signing secret is never sent to the frontend.
"""
import argparse
import asyncio
import hashlib
import hmac
import json
from pathlib import Path
import sys
import time
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import Payment

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('payment_id',type=int);parser.add_argument('--status',choices=['success','failed','cancelled'],default='success');parser.add_argument('--api-url',default='http://127.0.0.1:8000');args=parser.parse_args()
    async with SessionLocal() as db:
        payment=await db.get(Payment,args.payment_id)
        if not payment or payment.provider!='demo':raise SystemExit('Demo payment not found.')
        body={'event_id':f'operator-{payment.payment_id}-{args.status}','external_id':payment.external_id,'amount':str(payment.amount+payment.tip),'currency':payment.currency,'status':args.status}
    raw=json.dumps(body,separators=(',',':')).encode();stamp=str(int(time.time()))
    signature=hmac.new(get_settings().webhook_secret.get_secret_value().encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    async with httpx.AsyncClient() as client:
        response=await client.post(args.api_url.rstrip('/')+'/api/webhooks/demo',content=raw,headers={'Content-Type':'application/json','X-Webhook-Timestamp':stamp,'X-Webhook-Signature':signature})
        if response.status_code!=200:raise SystemExit(f'Webhook rejected: HTTP {response.status_code}')
    print('Signed demo confirmation accepted. No real money was moved.')

if __name__=='__main__':
    async def run():
        try:await main()
        finally:await engine.dispose()
    asyncio.run(run())
