import asyncio
import logging
from sqlalchemy import select, or_
from app.database import SessionLocal
from app.models import Payment, utcnow
from app.services.payments import reconcile

async def demo_confirmation_loop():
    """Server-side demo reconciliation; payment completion does not depend on browser polling."""
    while True:
        try:
            async with SessionLocal() as db:
                rows=await db.scalars(select(Payment).where(Payment.status.in_(['CREATED','PENDING']),Payment.provider=='demo',or_(Payment.provider_due_at<=utcnow(),Payment.qr_expires_at<=utcnow())).with_for_update(skip_locked=True).limit(100))
                for payment in rows:await reconcile(db,payment)
                await db.commit()
        except asyncio.CancelledError:raise
        except Exception:logging.getLogger('tipro').warning('demo_reconciliation_retry')
        await asyncio.sleep(.5)
