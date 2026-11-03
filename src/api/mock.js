import { merchants } from '../mocks/merchants.js'
import { employees } from '../mocks/employees.js'
import { qrs } from '../mocks/qrs.js'
import { seedPayments } from '../mocks/payments.js'

const KEY = 'tipro-demo-v1'
const wait = (ms = 160) => new Promise(resolve => setTimeout(resolve, ms))
const fail = (message, code = 'VALIDATION') => { throw Object.assign(new Error(message), { code }) }
const id = prefix => `${prefix}-${crypto.randomUUID()}`
const ROLES = ['merchant', 'employee', 'admin']
function write(data) {
  try { localStorage.setItem(KEY, JSON.stringify(data)) }
  catch { fail('Не удалось сохранить данные в браузере.', 'STORAGE') }
}
function read() {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved) {
      const d = JSON.parse(saved)
      if (d.version === 1) {
        d.employees = []; d.qrs = []; d.payments = []
        d.merchants = d.merchants.filter(m => !['m2', 'm3'].includes(m.id)); d.version = 2
      }
      if (d.version === 2) {
        d.employees = d.employees.map(e => ({ ...e, accessToken: id('invite'), goal: null }))
        d.qrs = d.qrs.map(q => ({ id: q.id, merchantId: q.merchantId, label: q.label, active: q.active, type: 'restaurant' }))
        d.version = 3
      }
      if (d.version === 3) {
        d.users = d.merchants.map(m => ({ id: `user-${m.id}`, role: 'merchant', merchantId: m.id, name: m.name, email: m.email, passwordHash: d.credentials?.[m.id] || null, demoAccount: m.id === 'm1' && !d.credentials?.[m.id] }))
        d.users.push({ id: 'platform-demo', role: 'admin', merchantId: null, name: 'Администратор платформы', email: 'admin@tipro.demo', passwordHash: null, demoAccount: true })
        d.employees = d.employees.map(e => {
          const { goal, ...rest } = e
          return { ...rest, accountId: null, goals: goal ? [goal] : [], activeGoalId: goal?.id || null }
        })
        if (d.session) {
          const user = d.session.role === 'admin' ? d.users.find(u => u.id === 'platform-demo') : d.users.find(u => u.merchantId === d.session.merchantId && u.role === 'merchant')
          d.session = user ? userSession(user) : null
        }
        delete d.credentials; d.version = 4; write(d)
      }
      if (d.version === 4) return d
    }
  } catch (error) { if (error.name !== 'SyntaxError') throw error }
  // Migrate the empty initial state through the same path as an existing installation.
  write({ version: 3, merchants: structuredClone(merchants), employees: structuredClone(employees), qrs: structuredClone(qrs), payments: seedPayments(), session: null, credentials: {} })
  return read()
}
function userSession(user) {
  return { userId: user.id, role: user.role, merchantId: user.merchantId || null, employeeId: user.employeeId || null }
}
function safeUser({ passwordHash, demoAccount, ...user }) { return user }
function current(d, role) {
  const user = d.users.find(u => u.id === d.session?.userId)
  if (!user || (role && user.role !== role)) fail('Недостаточно прав для этого действия.', 'UNAUTHORIZED')
  if (user.role === 'employee' && !d.employees.some(e => e.id === user.employeeId && e.active && e.accountId === user.id)) fail('Аккаунт сотрудника деактивирован. Обратитесь к администратору ресторана.', 'UNAUTHORIZED')
  return user
}
function merchantOnly(d, merchantId) {
  const user = current(d, 'merchant')
  if (user.merchantId !== merchantId) fail('Нет доступа к другому ресторану.', 'UNAUTHORIZED')
  return user
}
function employeeOnly(d, employeeId) {
  const user = current(d, 'employee')
  if (user.employeeId !== employeeId) fail('Можно изменять только свои цели.', 'UNAUTHORIZED')
  return d.employees.find(e => e.id === employeeId)
}
function activeGoal(e) { return e.goals.find(g => g.id === e.activeGoalId) || null }
function employeeView(e, privateData = false) {
  const result = { id: e.id, merchantId: e.merchantId, name: e.name, role: e.role, color: e.color, active: e.active, registered: Boolean(e.accountId), goal: activeGoal(e) }
  if (privateData) Object.assign(result, { goals: e.goals, activeGoalId: e.activeGoalId, accessToken: e.accountId ? null : e.accessToken })
  return result
}
function validQr(d, qrId) {
  const qr = d.qrs.find(q => q.id === qrId && q.active)
  if (!qr || !d.merchants.some(m => m.id === qr.merchantId)) fail('QR-код не найден или отключён.', 'INVALID_QR')
  return qr
}
function restaurant(d, qr) {
  const m = d.merchants.find(m => m.id === qr.merchantId)
  return { qr, merchant: { id: m.id, name: m.name, location: m.location }, employees: d.employees.filter(e => e.merchantId === m.id && e.active).map(e => employeeView(e)) }
}
function invitationEmployee(d, token) {
  const employee = typeof token === 'string' && token ? d.employees.find(e => e.accessToken === token && e.active && !e.accountId) : null
  if (!employee) fail('Приглашение недействительно, уже использовано или сотрудник неактивен.', 'INVALID_ACCESS')
  return employee
}
async function hash(value) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))].map(b => b.toString(16).padStart(2, '0')).join('')
}
export const mockApi = {
  async session() {
    await wait(40); const d = read()
    if (!d.session) return null
    try { current(d); return d.session } catch { d.session = null; write(d); return null }
  },
  async demo(role = 'merchant') {
    await wait(); const d = read()
    const user = d.users.find(u => u.id === (role === 'admin' ? 'platform-demo' : 'user-m1'))
    if (!['merchant', 'admin'].includes(role) || !user) fail('Демоаккаунт недоступен.')
    d.session = userSession(user); write(d); return d.session
  },
  async login({ email, password }) {
    await wait(); const passwordHash = await hash(password); const d = read()
    const user = d.users.find(u => u.email === email.trim().toLowerCase())
    if (!user || (user.demoAccount ? password !== 'Demo12345' : user.passwordHash !== passwordHash)) fail('Неверный email или пароль.')
    // Check activity before changing the current session.
    if (user.role === 'employee' && !d.employees.some(e => e.id === user.employeeId && e.active)) fail('Сотрудник деактивирован.', 'UNAUTHORIZED')
    d.session = userSession(user); write(d); return d.session
  },
  async register({ role = 'merchant', name, restaurantName, email, password, invite }) {
    await wait(); name = name?.trim(); email = email?.trim().toLowerCase()
    if (!ROLES.includes(role) || !name || name.length < 2 || name.length > 100 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email || '') || typeof password !== 'string' || password.length < 8) fail('Проверьте роль, имя, email и пароль (от 8 символов).')
    if (role === 'merchant' && !(restaurantName || name)?.trim()) fail('Укажите название ресторана.')
    const passwordHash = await hash(password); const d = read()
    if (d.users.some(u => u.email === email)) fail('Аккаунт с таким email уже существует.')
    const user = { id: id('user'), role, name, email, passwordHash, merchantId: null, employeeId: null }
    if (role === 'merchant') {
      const merchant = { id: id('m'), name: (restaurantName || name).trim(), email, location: 'Ресторан', createdAt: new Date().toISOString() }
      if (merchant.name.length > 100) fail('Название ресторана — до 100 символов.')
      d.merchants.push(merchant); user.merchantId = merchant.id
    } else if (role === 'employee') {
      const e = invitationEmployee(d, invite)
      user.employeeId = e.id; user.merchantId = e.merchantId; e.accountId = user.id
      // The restaurant controls the public employee name and position.
    }
    // Self-registration of platform administrators is available only in this local prototype.
    d.users.push(user); d.session = userSession(user); write(d); return d.session
  },
  async invitation(token) {
    await wait(); const d = read(); const e = invitationEmployee(d, token)
    return { name: e.name, position: e.role, restaurantName: d.merchants.find(m => m.id === e.merchantId).name }
  },
  async logout() { const d = read(); d.session = null; write(d) },
  async workspace() {
    await wait(); const d = read(); const user = current(d)
    if (user.role === 'admin') return { user: safeUser(user), merchant: null, employees: [], qrs: [], payments: [] }
    const m = d.merchants.find(m => m.id === user.merchantId)
    if (user.role === 'employee') {
      const e = d.employees.find(e => e.id === user.employeeId)
      const self = employeeView(e, true); delete self.accessToken
      return { user: safeUser(user), merchant: { id: m.id, name: m.name, location: m.location }, employees: [self], qrs: [], payments: d.payments.filter(p => p.employeeId === e.id && p.merchantId === m.id) }
    }
    return { user: safeUser(user), merchant: m, employees: d.employees.filter(e => e.merchantId === m.id).map(e => employeeView(e, true)), qrs: d.qrs.filter(q => q.merchantId === m.id), payments: d.payments.filter(p => p.merchantId === m.id) }
  },
  async saveEmployee(employee) {
    await wait(); const d = read(); const user = current(d, 'merchant')
    const name = employee.name?.trim(), role = employee.role?.trim()
    if (!name || name.length > 80 || !role || role.length > 60) fail('Укажите имя (до 80 символов) и должность (до 60 символов).')
    let saved
    if (employee.id) {
      const e = d.employees.find(e => e.id === employee.id && e.merchantId === user.merchantId)
      if (!e) fail('Сотрудник не найден.', 'UNAUTHORIZED')
      Object.assign(e, { name, role, active: Boolean(employee.active) }); saved = e
    } else {
      saved = { id: id('e'), merchantId: user.merchantId, name, role, active: true, color: 'sage', accessToken: id('invite'), accountId: null, goals: [], activeGoalId: null }
      d.employees.push(saved)
    }
    write(d); return employeeView(saved, true)
  },
  async saveGoal(employeeId, { id: goalId, title, target }) {
    await wait(); const d = read(); const employee = employeeOnly(d, employeeId)
    title = title?.trim(); target = Number(target)
    if (!title || title.length > 100 || !Number.isInteger(target) || target < 100 || target > 10000000) fail('Укажите цель до 100 символов и целую сумму от 100 до 10 000 000 ₽.')
    if (goalId) {
      const goal = employee.goals.find(g => g.id === goalId)
      if (!goal) fail('Цель не найдена.', 'UNAUTHORIZED')
      Object.assign(goal, { title, target })
    } else {
      const goal = { id: id('goal'), title, target, raised: 0 }
      employee.goals.push(goal); employee.activeGoalId = goal.id
    }
    write(d); return employeeView(employee, true)
  },
  async activateGoal(employeeId, goalId) {
    await wait(); const d = read(); const e = employeeOnly(d, employeeId)
    if (!e.goals.some(g => g.id === goalId)) fail('Цель не найдена.', 'UNAUTHORIZED')
    e.activeGoalId = goalId; write(d)
  },
  async createQr({ label, receiptNumber, billAmount } = {}) {
    await wait(); const d = read(); const user = current(d, 'merchant')
    if (label && (typeof label !== 'string' || label.trim().length > 80)) fail('Название QR-кода — до 80 символов.')
    const hasReceipt = receiptNumber !== undefined || billAmount !== undefined
    if (hasReceipt && (typeof receiptNumber !== 'string' || !receiptNumber.trim() || receiptNumber.trim().length > 40 || !Number.isInteger(Number(billAmount)) || Number(billAmount) < 1 || Number(billAmount) > 10000000)) fail('Укажите номер чека (до 40 символов) и целую сумму от 1 до 10 000 000 ₽.')
    const createdAt = new Date().toISOString()
    const qr = { id: id('qr'), merchantId: user.merchantId, type: 'restaurant', label: label?.trim() || (hasReceipt ? `Чек № ${receiptNumber.trim()}` : 'QR-код ресторана'), active: true, createdAt, receipt: hasReceipt ? { number: receiptNumber.trim(), billAmount: Number(billAmount) } : null }
    d.qrs.push(qr); write(d); return qr
  },
  async toggleQr(qrId) {
    await wait(); const d = read(); const qr = d.qrs.find(q => q.id === qrId)
    if (!qr) fail('QR-код не найден.')
    merchantOnly(d, qr.merchantId); qr.active = !qr.active; write(d)
  },
  async resolveQr(qrId) { await wait(); const d = read(); return restaurant(d, validQr(d, qrId)) },
  async resolveRestaurant(merchantId, qrId) {
    await wait(); const d = read(); const qr = validQr(d, qrId)
    if (qr.merchantId !== merchantId) fail('QR-код относится к другому ресторану.', 'INVALID_QR')
    return restaurant(d, qr)
  },
  async pay({ qrId, employeeId, amount, scenario = 'success', signal }) {
    await wait(1100); const d = read(); const qr = validQr(d, qrId)
    const employee = d.employees.find(e => e.id === employeeId && e.merchantId === qr.merchantId && e.active)
    if (!employee) fail('Выберите активного сотрудника этого ресторана.', 'INVALID_EMPLOYEE')
    if (!['success', 'declined', 'cancelled'].includes(scenario)) fail('Неизвестный сценарий оплаты.')
    amount = Number(amount)
    if (!Number.isInteger(amount) || amount < 10 || amount > 50000) fail('Введите целую сумму от 10 до 50 000 ₽.')
    const status = signal?.aborted || scenario === 'cancelled' ? 'cancelled' : scenario === 'declined' ? 'declined' : 'success'
    const goal = activeGoal(employee)
    const payment = { id: id('tx'), merchantId: qr.merchantId, employeeId, amount, status, createdAt: new Date().toISOString(), qrId, goalId: goal?.id || null }
    d.payments.push(payment); if (status === 'success' && goal) goal.raised += amount
    write(d); return payment
  },
  async admin() {
    await wait(); const d = read(); current(d, 'admin')
    return { merchants: d.merchants, employees: d.employees.map(e => employeeView(e)), payments: d.payments }
  },
}
