from app.core.security import invite_token, qr_token

STATUS = {'SUCCESS': 'success', 'DECLINED': 'declined', 'CANCELED': 'cancelled', 'PENDING': 'pending'}

def merchant_view(m):
    return {'id': str(m.merchant_id), 'name': m.name, 'email': m.contact_email or '', 'location': m.description or '', 'status': m.status, 'currency': m.currency, 'language': m.language, 'tipPercentages': m.tip_percentages, 'paymentMethods': m.payment_methods, 'createdAt': m.created_at}

def goal_view(g):
    return {'id': str(g.goal_id), 'title': g.title, 'target': str(g.target), 'raised': str(g.raised), 'currency': g.currency}

def employee_view(e, goals, private=False, invitations=False):
    own_goals = [g for g in goals if g.employee_id == e.employee_id]
    active = next((g for g in own_goals if g.active), None)
    result = {'id': str(e.employee_id), 'merchantId': str(e.merchant_id), 'name': e.name, 'role': e.title, 'active': e.active, 'registered': bool(e.auth_email), 'color': 'sage', 'goal': goal_view(active) if active else None}
    if private:
        result.update(goals=[goal_view(g) for g in own_goals], activeGoalId=str(active.goal_id) if active else None)
    if invitations:
        result['accessToken'] = invite_token(e)
    return result

def qr_view(q):
    return {'id': qr_token(q), 'nonce': q.nonce, 'exp': q.exp, 'sign': q.signature, 'merchantId': str(q.merchant_id), 'employeeId': str(q.employee_id) if q.employee_id else None, 'type': 'restaurant', 'label': q.label, 'active': q.active and q.token_version == 'v1', 'createdAt': q.created_at, 'expiresAt': q.expires_at, 'currency': q.currency, 'receipt': {'number': q.receipt_number, 'billAmount': str(q.bill_amount) if q.bill_amount is not None else None} if q.receipt_number else None}

def payment_view(p, public=False):
    result = {'id': str(p.payment_id), 'merchantId': str(p.merchant_id), 'employeeId': str(p.employee_id), 'amount': str(p.tip), 'billAmount': str(p.amount), 'currency': p.currency, 'status': STATUS[p.status], 'createdAt': p.created_at, 'updatedAt': p.updated_at, 'qrId': str(p.qr_id) if p.qr_id else None, 'goalId': str(p.goal_id) if p.goal_id else None}
    if p.failure_reason:
        result['errorCode'] = p.failure_reason
    if public:
        result['publicToken'] = p.public_token
    return result
