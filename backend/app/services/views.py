from app.core.security import invite_token, qr_token
from app.models import utcnow

STATUS = {'CREATED': 'created', 'SUCCESS': 'success', 'DECLINED': 'declined', 'CANCELED': 'cancelled', 'PENDING': 'pending'}

def merchant_view(m):
    return {'id': str(m.merchant_id), 'name': m.name, 'email': m.contact_email or '', 'location': m.description or '', 'status': m.status, 'currency': m.currency, 'language': m.language, 'tipPercentages': m.tip_percentages, 'paymentMethods': m.payment_methods, 'createdAt': m.created_at, 'approvedAt': m.approved_at, 'approvedBy': str(m.approved_by) if m.approved_by else None}

def goal_view(g):
    return {'id': str(g.goal_id), 'title': g.title, 'target': str(g.target), 'raised': str(g.raised), 'currency': g.currency}

def employee_view(e, goals, private=False, invitations=False):
    own_goals = [g for g in goals if g.employee_id == e.employee_id]
    active = next((g for g in own_goals if g.active), None)
    result = {'id': str(e.employee_id), 'merchantId': str(e.merchant_id), 'name': e.name, 'role': e.title, 'active': e.active, 'registered': bool(e.auth_email), 'color': 'sage', 'goal': goal_view(active) if active else None}
    if private:
        result.update(paymentDetails=e.payment_details, goals=[goal_view(g) for g in own_goals], activeGoalId=str(active.goal_id) if active else None)
    if invitations:
        result['accessToken'] = invite_token(e)
    return result

def qr_view(q):
    state='legacy' if q.token_version!='v3' else 'used' if q.used_at else 'expired' if not q.expires_at or q.expires_at<=utcnow() else 'active' if q.active else 'disabled'
    return {'state': state, 'usedAt': q.used_at, 'singleUse': q.token_version == 'v3', 'id': qr_token(q), 'nonce': q.nonce, 'exp': q.exp, 'sign': q.signature, 'merchantId': str(q.merchant_id), 'employeeId': str(q.employee_id) if q.employee_id else None, 'type': 'employee', 'label': q.label, 'active': state == 'active', 'createdAt': q.created_at, 'expiresAt': q.expires_at, 'currency': q.currency, 'receipt': {'id': str(q.receipt_id), 'number': q.receipt_number, 'billAmount': str(q.bill_amount) if q.bill_amount is not None else None} if q.receipt_number else None}

def payment_view(p, public=False):
    result = {'id': str(p.payment_id), 'merchantId': str(p.merchant_id), 'employeeId': str(p.employee_id), 'amount': str(p.tip), 'billAmount': str(p.amount), 'amountTotal': str(p.amount+p.tip), 'currency': p.currency, 'status': STATUS[p.status], 'createdAt': p.created_at, 'updatedAt': p.updated_at, 'qrId': str(p.qr_id) if p.qr_id else None, 'goalId': str(p.goal_id) if p.goal_id else None}
    if p.failure_reason:
        result['errorCode'] = p.failure_reason
    if public:
        result['publicToken'] = p.public_token
    return result
