import { merchants } from '../mocks/merchants.js'
import { employees } from '../mocks/employees.js'
import { qrs } from '../mocks/qrs.js'
import { seedPayments } from '../mocks/payments.js'
const KEY = 'tipro-demo-v1'
const wait = (ms = 260) => new Promise(resolve => setTimeout(resolve, ms))
const fail = (message, code = 'VALIDATION') => { throw Object.assign(new Error(message), { code }) }
function read() {
  try { const saved = localStorage.getItem(KEY); if (saved) { const data = JSON.parse(saved); if (data.version === 1) {
    // One-time transition from the populated prototype to a fresh account.
    data.version = 2
    data.employees = []; data.qrs = []; data.payments = []
    data.merchants = data.merchants.filter(m => !['m2', 'm3'].includes(m.id))
    write(data)
  }
  if (data.version === 2) return data } } catch (error) { if (error.name !== 'SyntaxError') throw error }
  const data = { version: 2, merchants: structuredClone(merchants), employees: structuredClone(employees), qrs: structuredClone(qrs), payments: seedPayments(), session: null, credentials: {} }
  write(data); return data
}
function write(data) { try { localStorage.setItem(KEY, JSON.stringify(data)) } catch { fail('Не удалось сохранить данные. Разрешите localStorage или освободите место.', 'STORAGE') } }
const id = (prefix) => `${prefix}-${crypto.randomUUID()}`
async function hash(value) { return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))].map(b => b.toString(16).padStart(2, '0')).join('') }
function own(data, merchantId) { if (!data.session || (data.session.role !== 'admin' && data.session.merchantId !== merchantId)) fail('Войдите в кабинет ресторана.', 'UNAUTHORIZED') }
function validQr(data, qrId) {
  const qr = data.qrs.find(q => q.id === qrId)
  if (!qr || !qr.active || !data.employees.find(e => e.id === qr.employeeId && e.active)) fail('QR-код не найден или больше не действует.', 'INVALID_QR')
  if (qr.type === 'receipt' && qr.used) fail('По этому чеку уже оставили чаевые.', 'USED_QR')
  return qr
}
export const mockApi = {
  async session() { await wait(80); return read().session },
  async demo(role = 'merchant') { await wait(); const d = read(); d.session = { role, merchantId: 'm1' }; write(d); return d.session },
  async login({ email, password }) {
    await wait(); const d = read(); const m = d.merchants.find(m => m.email === email.trim().toLowerCase())
    const stored = m && d.credentials[m.id]
    if (!m || (stored ? stored !== await hash(password) : !(m.id === 'm1' && password === 'Demo12345'))) fail('Неверный email или пароль.')
    d.session = { role: 'merchant', merchantId: m.id }; write(d); return d.session
  },
  async register({ name, email, password }) {
    await wait(); name = name.trim(); email = email.trim().toLowerCase()
    if (name.length < 2 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || password.length < 8) fail('Проверьте название, email и пароль (от 8 символов).')
    const passwordHash = await hash(password); const d = read()
    if (d.merchants.some(m => m.email === email)) fail('Ресторан с таким email уже зарегистрирован.')
    const m = { id: id('m'), name, email, location: 'Новый ресторан', createdAt: new Date().toISOString() }
    d.merchants.push(m); d.credentials[m.id] = passwordHash; d.session = { role: 'merchant', merchantId: m.id }; write(d); return d.session
  },
  async logout() { const d = read(); d.session = null; write(d) },
  async workspace() {
    await wait(); const d = read(); if (!d.session) fail('Войдите в систему.', 'UNAUTHORIZED')
    const mid = d.session.merchantId
    return { merchant: d.merchants.find(m => m.id === mid), employees: d.employees.filter(e => e.merchantId === mid), qrs: d.qrs.filter(q => q.merchantId === mid), payments: d.payments.filter(p => p.merchantId === mid) }
  },
  async saveEmployee(employee) {
    await wait(); const d = read(); const mid = d.session?.merchantId; own(d, mid)
    if (!employee.name?.trim() || !employee.role?.trim()) fail('Укажите имя и должность.')
    if (employee.id) { const e = d.employees.find(e => e.id === employee.id && e.merchantId === mid); if (!e) fail('Сотрудник не найден.'); Object.assign(e, { name: employee.name.trim(), role: employee.role.trim(), active: Boolean(employee.active) }) }
    else d.employees.push({ id: id('e'), merchantId: mid, name: employee.name.trim(), role: employee.role.trim(), active: true, color: 'sage' })
    write(d)
  },
  async createQr({ employeeId, type, label, bill }) {
    await wait(); const d = read(); const mid = d.session?.merchantId; own(d, mid)
    if (!d.employees.some(e => e.id === employeeId && e.merchantId === mid && e.active)) fail('Выберите активного сотрудника.')
    if (!['personal', 'receipt'].includes(type)) fail('Неизвестный тип QR-кода.')
    if (type === 'receipt' && (!(Number(bill) > 0) || !Number.isFinite(Number(bill)))) fail('Введите сумму чека.')
    const qr = { id: id('qr'), merchantId: mid, employeeId, type, label: label?.trim() || (type === 'personal' ? 'Персональный QR' : 'Новый чек'), bill: type === 'receipt' ? Number(bill) : null, active: true, used: false }
    d.qrs.push(qr); write(d); return qr
  },
  async toggleQr(qrId) { await wait(); const d = read(); const q = d.qrs.find(q => q.id === qrId); if (!q) fail('QR-код не найден.'); own(d, q.merchantId); q.active = !q.active; write(d) },
  async resolveQr(qrId) { await wait(); const d = read(); const qr = validQr(d, qrId); return { qr, employee: d.employees.find(e => e.id === qr.employeeId), merchant: d.merchants.find(m => m.id === qr.merchantId) } },
  async pay({ qrId, amount, scenario = 'success', signal }) {
    await wait(1300)
    const d = read(); const qr = validQr(d, qrId)
    if (!['success', 'declined', 'cancelled'].includes(scenario)) fail('Неизвестный сценарий оплаты.')
    amount = Number(amount)
    if (!Number.isFinite(amount) || amount < 10 || amount > 50000 || !Number.isInteger(amount)) fail('Введите целую сумму от 10 до 50 000 ₽.')
    const status = signal?.aborted || scenario === 'cancelled' ? 'cancelled' : scenario === 'declined' ? 'declined' : 'success'
    const payment = { id: id('tx'), merchantId: qr.merchantId, employeeId: qr.employeeId, amount, status, createdAt: new Date().toISOString(), qrId }
    d.payments.push(payment); if (status === 'success' && qr.type === 'receipt') qr.used = true
    write(d); return payment
  },
  async admin() { await wait(); const d = read(); if (d.session?.role !== 'admin') fail('Нужен режим администратора.', 'UNAUTHORIZED'); return { merchants: d.merchants, employees: d.employees, payments: d.payments } },
}
