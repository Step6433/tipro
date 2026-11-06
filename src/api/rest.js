import { request, allPages, query, setAccessToken } from './http'
import { browserTimeZone } from '../utils/dates'
import { createIdempotencyKey } from '../utils/idempotency'

const amountFields = ['amount', 'billAmount', 'target', 'raised', 'total', 'average', 'amountTotal', 'avgTipPct', 'successRate']
// Decimal strings stay exact over the wire. Numbers here are for UI display only;
// the server independently validates and calculates every monetary operation.
function normalize(value) {
  if (Array.isArray(value)) return value.map(normalize)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, amountFields.includes(key) && item !== null ? Number(item) : normalize(item)]))
}
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
const attempts = new Map()
function attemptKey(qrId, employeeId) { return `tipro-payment:${qrId}:${employeeId}` }
function getAttempt(key) { try { return attempts.get(key) || JSON.parse(sessionStorage.getItem(key) || 'null') } catch { return attempts.get(key) } }
function saveAttempt(key, value) { attempts.set(key, value); try { sessionStorage.setItem(key, JSON.stringify(value)) } catch { /* In-memory retry remains available. */ } }
function removeAttempt(key) { attempts.delete(key); try { sessionStorage.removeItem(key) } catch { /* Storage is optional. */ } }

function clearPaymentToken(token) {
  const keys=new Set(attempts.keys())
  try { for(let i=0;i<sessionStorage.length;i++){const key=sessionStorage.key(i);if(key?.startsWith('tipro-payment:'))keys.add(key)} } catch { /* Optional storage. */ }
  for(const key of keys)if(getAttempt(key)?.publicToken===token)removeAttempt(key)
}

export const restApi = {
  async capabilities() { return request('/capabilities') },
  async session() {
    try { return (await request('/auth/me')).session }
    catch (e) { if (e.status === 401 || e.code === 'MERCHANT_BLOCKED') { setAccessToken(null); return null } throw e }
  },
  async login({ email, password }) {
    const data = await request('/auth/login', { method: 'POST', body: { email, password } })
    setAccessToken(data.accessToken); return data.session
  },
  async register({ role, name, restaurantName, email, password, invite }) {
    const body = { role, name, email, password }
    if (role === 'merchant') body.restaurantName = restaurantName
    if (role === 'employee') body.invite = invite
    const data = await request('/auth/register', { method: 'POST', body })
    setAccessToken(data.accessToken); return data.session
  },
  async logout() { try { await request('/auth/logout', { method: 'POST' }) } catch (e) { if (e.status !== 401) throw e } finally { setAccessToken(null) } },
  invitation: token => request(`/auth/invitations/${encodeURIComponent(token)}`),
  async workspace({ currency } = {}) {
    const core = await request('/workspace')
    currency = currency || core.merchant?.currency || 'RUB'
    if (core.user.role === 'admin') return { ...core, employees: [], qrs: [], payments: [], analytics: null, currency }
    const timezone = browserTimeZone()
    const [employees, qrs, payments, analytics] = await Promise.all([
      allPages('/employees'), core.user.role === 'merchant' ? allPages('/qrs') : [],
      allPages('/payments', { currency, timezone }), request('/analytics' + query({ currency, timezone })),
    ])
    return normalize({ ...core, employees, qrs, payments, analytics, currency })
  },
  async saveEmployee({ id, name, role, active = true, paymentDetails = '' }) { return normalize(await request(id ? `/employees/${id}` : '/employees', { method: id ? 'PATCH' : 'POST', body: { name, role, active, paymentDetails } })) },
  inviteEmployee: id => request(`/employees/${id}/invitation`, { method: 'POST' }),
  async saveGoal(employeeId, { id, title, target, currency = 'RUB' }) { return normalize(await request(`/employees/${employeeId}/goals${id ? `/${id}` : ''}`, { method: id ? 'PATCH' : 'POST', body: { title, target: String(target), currency } })) },
  activateGoal: (employeeId, goalId) => request(`/employees/${employeeId}/goals/${goalId}/active`, { method: 'PUT' }),
  async createQr({ employeeId, currency, label, receiptNumber, billAmount } = {}) { return normalize(await request('/qrs', { method: 'POST', body: { employeeId: Number(employeeId), billAmount: String(billAmount), ...(receiptNumber ? { receiptNumber } : {}), ...(currency ? { currency } : {}), ...(label ? { label } : {}) } })) },
  async toggleQr(token) {
    const list = await allPages('/qrs')
    const qr = list.find(q => q.id === token)
    if (!qr) throw new Error('QR-код не найден.')
    return request(`/qrs/${encodeURIComponent(token)}`, { method: 'PATCH', body: { active: !qr.active } })
  },
  async resolveQr(token) { return normalize(await request(`/public/qrs/${encodeURIComponent(token)}`)) },
  async resolveRestaurant(id, token) { return normalize(await request(`/public/restaurants/${id}` + query({ qr: token }))) },
  async preparePayment({ qrId, employeeId, receiptId, amount, percent, currency = 'RUB', scenario = 'success' }) {
    const key = attemptKey(qrId, employeeId)
    const body = { employeeId: Number(employeeId), receiptId: Number(receiptId), ...(percent !== undefined ? { percent: String(percent) } : { amount: String(amount) }), currency, scenario, method: 'demo' }
    const fingerprint = JSON.stringify(body)
    let attempt = getAttempt(key)
    if (attempt && attempt.fingerprint !== fingerprint) {
      // Resolve an uncertain previous attempt before allowing another amount.
      if (!attempt.publicToken) throw new Error('Предыдущий запрос не подтверждён. Повторите с прежней суммой и сценарием.')
      const previous = await request(`/public/payments/${attempt.publicToken}`)
      if (['created','pending'].includes(previous.status)) throw new Error('Предыдущий платёж ещё ожидает подтверждения. Сначала проверьте или отмените его.')
      removeAttempt(key); attempt = null
    }
    if (!attempt) { attempt = { idempotencyKey: createIdempotencyKey(), fingerprint }; saveAttempt(key, attempt) }
    let payment
    try { payment = await request(`/public/qrs/${encodeURIComponent(qrId)}/payments`, { method: 'POST', headers: { 'Idempotency-Key': attempt.idempotencyKey }, body }) }
    catch(e) { if(e.status && e.status < 500 && e.status !== 409)removeAttempt(key); throw e }
    attempt.publicToken = payment.publicToken; saveAttempt(key, attempt)
    return normalize(payment)
  },
  async confirmPayment(token, { wait = true } = {}) {
    let result = await request(`/public/payments/${encodeURIComponent(token)}/confirm`, { method: 'POST' })
    for (let i=0; wait && i<12 && result.status==='pending';i++) {
      await sleep(300); result=await this.checkPayment(token)
    }
    if (!['created','pending'].includes(result.status)) clearPaymentToken(token)
    return normalize(result)
  },
  async pay(options) {
    const payment = await this.preparePayment(options)
    if (options.signal?.aborted && payment.status==='created') return this.cancelPayment(payment.publicToken)
    return this.confirmPayment(payment.publicToken, {wait: options.scenario!=='pending'})
  },
  async resumePayment(qrId, employeeIds) {
    for (const employeeId of employeeIds) {
      const key = attemptKey(qrId, employeeId), attempt = getAttempt(key)
      if (!attempt) continue
      if (!attempt.publicToken) {
        const payment = await request(`/public/qrs/${encodeURIComponent(qrId)}/payments`, { method: 'POST', headers: { 'Idempotency-Key': attempt.idempotencyKey }, body: JSON.parse(attempt.fingerprint) })
        attempt.publicToken = payment.publicToken; saveAttempt(key, attempt)
      }
      const payment = await this.checkPayment(attempt.publicToken)
      if (!['created','pending'].includes(payment.status)) removeAttempt(key)
      return payment
    }
    return null
  },
  async checkPayment(token) { const result=normalize(await request(`/public/payments/${encodeURIComponent(token)}`)); if(!['created','pending'].includes(result.status))clearPaymentToken(token); return result },
  async cancelPayment(token) { const result=normalize(await request(`/public/payments/${encodeURIComponent(token)}/cancel`, { method: 'POST' })); if(!['created','pending'].includes(result.status))clearPaymentToken(token); return result },
  async analytics(filters = {}) { return normalize(await request('/analytics' + query({timezone:browserTimeZone(),...filters}))) },
  async settings(id, body) { return request(`/restaurants/${id}/settings`, { method: 'PATCH', body }) },
  async exportPayments(filters = {}) {
    const response = await request('/payments/export' + query({timezone:browserTimeZone(),...filters}), { raw: true })
    return response.blob()
  },
  blockRestaurant: id => request(`/admin/restaurants/${encodeURIComponent(id)}/block`, { method: 'POST' }),
  unblockRestaurant: id => request(`/admin/restaurants/${encodeURIComponent(id)}/unblock`, { method: 'POST' }),
  approveRestaurant: id => request(`/admin/restaurants/${encodeURIComponent(id)}/approve`, { method: 'POST' }),
  async admin({ currency = 'RUB' } = {}) {
    const timezone=browserTimeZone()
    const [overview, merchants, employees, payments, notifications] = await Promise.all([
      request('/admin/overview' + query({ currency, timezone })), allPages('/restaurants'), allPages('/employees'), allPages('/payments', { currency, timezone }), allPages('/admin/notifications'),
    ])
    return normalize({ ...overview, merchants, employees, payments, notifications })
  },
}
