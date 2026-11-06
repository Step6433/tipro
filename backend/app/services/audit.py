from app.models import AuditEvent

def record(db, payment, action, previous, actor='system'):
    db.add(AuditEvent(payment_id=payment.payment_id, qr_id=payment.qr_id,
        merchant_id=payment.merchant_id, action=action, from_status=previous,
        to_status=payment.status, amount_total=payment.amount+payment.tip, actor=actor))
