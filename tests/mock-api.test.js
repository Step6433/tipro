import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { mockApi as api } from '../src/api/mock.js'
let values
beforeEach(() => {
  values = new Map()
  globalThis.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
})
const password = 'Test12345'
async function restaurantFixture() {
  await api.register({ role: 'merchant', name: 'Руководитель', restaurantName: 'Наш ресторан', email: 'owner@example.ru', password })
  await api.saveEmployee({ name: 'Анна Смирнова', role: 'Официант' })
  await api.saveEmployee({ name: 'Иван Петров', role: 'Бармен' })
  const workspace = await api.workspace()
  const qr = await api.createQr({ label: 'Стол 1' })
  return { merchant: workspace.merchant, anna: workspace.employees[0], ivan: workspace.employees[1], qr }
}
async function join(employee, email) {
  return api.register({ role: 'employee', name: employee.name, email, password, invite: employee.accessToken })
}
async function login(email) { await api.login({ email, password }) }

test('all three roles register and sign in to separate accounts; a new restaurant is empty', async () => {
  await api.register({ role: 'merchant', name: 'Алексей', restaurantName: 'Тест', email: 'owner@example.ru', password })
  const workspace = await api.workspace()
  assert.equal(workspace.user.role, 'merchant')
  assert.equal(workspace.user.passwordHash, undefined)
  assert.equal(workspace.merchant.name, 'Тест')
  for (const key of ['employees', 'qrs', 'payments']) assert.deepEqual(workspace[key], [])
  await api.register({ role: 'admin', name: 'Админ', email: 'admin@example.ru', password })
  assert.equal((await api.session()).role, 'admin')
  assert.ok((await api.admin()).merchants.some(m => m.name === 'Тест'))
  await api.logout(); await login('owner@example.ru')
  assert.equal((await api.session()).role, 'merchant')
  await assert.rejects(api.admin(), { code: 'UNAUTHORIZED' })
  await assert.rejects(api.register({ role: 'guest', name: 'Гость', email: 'g@example.ru', password }))
  await assert.rejects(api.register({ role: 'admin', name: 'Копия', email: 'OWNER@example.ru', password }))
})

test('employee registration requires a valid unused invitation and preserves the employee record', async () => {
  const { anna } = await restaurantFixture()
  assert.equal((await api.invitation(anna.accessToken)).name, anna.name)
  await assert.rejects(api.register({ role: 'employee', name: 'Анна', email: 'anna@example.ru', password }), { code: 'INVALID_ACCESS' })
  const session = await join(anna, 'anna@example.ru')
  assert.equal(session.role, 'employee'); assert.equal(session.employeeId, anna.id)
  const workspace = await api.workspace()
  assert.equal(workspace.employees.length, 1)
  assert.equal(workspace.employees[0].registered, true)
  assert.equal(workspace.employees[0].accessToken, undefined)
  await assert.rejects(api.invitation(anna.accessToken), { code: 'INVALID_ACCESS' })
  await assert.rejects(join(anna, 'another@example.ru'), { code: 'INVALID_ACCESS' })
  await api.logout(); await login('anna@example.ru')
  assert.equal((await api.session()).employeeId, anna.id)
})

test('each employee sees only their payments, statistics and goals; guest tips update the selected goal', async () => {
  const { anna, ivan, qr, merchant } = await restaurantFixture()
  await join(anna, 'anna@example.ru')
  await api.saveGoal(anna.id, { title: 'Путешествие', target: 50000 })
  await join(ivan, 'ivan@example.ru')
  await api.saveGoal(ivan.id, { title: 'Гитара', target: 20000 })
  await api.logout()
  const page = await api.resolveRestaurant(merchant.id, qr.id)
  assert.equal(page.employees.length, 2)
  for (const e of page.employees) {
    assert.equal(e.accessToken, undefined); assert.equal(e.goals, undefined); assert.equal(e.accountId, undefined)
  }
  assert.equal(page.merchant.email, undefined)
  await api.pay({ qrId: qr.id, employeeId: anna.id, amount: 500 })
  await api.pay({ qrId: qr.id, employeeId: ivan.id, amount: 300 })
  await login('anna@example.ru')
  let workspace = await api.workspace()
  assert.deepEqual(workspace.employees.map(e => e.id), [anna.id])
  assert.deepEqual(workspace.qrs, [])
  assert.equal(workspace.payments.length, 1)
  assert.equal(workspace.payments[0].amount, 500)
  assert.equal(workspace.employees[0].goal.raised, 500)
  await login('ivan@example.ru')
  workspace = await api.workspace()
  assert.equal(workspace.payments.length, 1); assert.equal(workspace.payments[0].amount, 300)
  assert.equal(workspace.employees[0].goal.raised, 300)
  await login('owner@example.ru')
  workspace = await api.workspace()
  assert.equal(workspace.payments.reduce((s, p) => s + p.amount, 0), 800)
  assert.equal(workspace.employees.length, 2)
})

test('employee and platform admin cannot manage restaurant QR, employees or other employees goals', async () => {
  const { anna, ivan, qr } = await restaurantFixture()
  await join(anna, 'anna@example.ru')
  await assert.rejects(api.admin(), { code: 'UNAUTHORIZED' })
  await assert.rejects(api.createQr(), { code: 'UNAUTHORIZED' })
  await assert.rejects(api.toggleQr(qr.id), { code: 'UNAUTHORIZED' })
  await assert.rejects(api.saveEmployee({ ...anna, name: 'Другой' }), { code: 'UNAUTHORIZED' })
  await assert.rejects(api.saveGoal(ivan.id, { title: 'Чужая цель', target: 1000 }), { code: 'UNAUTHORIZED' })
  // Possessing an old invitation cannot replace signed-in employee identity.
  await assert.rejects(api.saveGoal(anna.accessToken, { title: 'По ссылке', target: 1000 }), { code: 'UNAUTHORIZED' })
  await api.register({ role: 'admin', name: 'Админ', email: 'admin@example.ru', password })
  assert.equal((await api.admin()).employees.length, 2)
  await assert.rejects(api.createQr(), { code: 'UNAUTHORIZED' })
  await assert.rejects(api.saveGoal(anna.id, { title: 'Цель', target: 1000 }), { code: 'UNAUTHORIZED' })
  await api.register({ role: 'merchant', name: 'Другой', restaurantName: 'Другой ресторан', email: 'other@example.ru', password })
  assert.deepEqual((await api.workspace()).payments, [])
  await assert.rejects(api.toggleQr(qr.id), { code: 'UNAUTHORIZED' })
  await assert.rejects(api.saveEmployee({ ...anna, name: 'Другое имя' }), { code: 'UNAUTHORIZED' })
})

test('multiple goals retain progress; only the current goal receives successful tips', async () => {
  const { anna, qr } = await restaurantFixture()
  await join(anna, 'anna@example.ru')
  await api.saveGoal(anna.id, { title: 'Обучение', target: 10000 })
  const first = (await api.workspace()).employees[0].goal
  await api.pay({ qrId: qr.id, employeeId: anna.id, amount: 400 })
  await api.saveGoal(anna.id, { title: 'Поездка', target: 20000 })
  let self = (await api.workspace()).employees[0]
  assert.equal(self.goals.length, 2); assert.equal(self.goals[0].raised, 400)
  assert.notEqual(self.activeGoalId, first.id)
  await api.pay({ qrId: qr.id, employeeId: anna.id, amount: 300 })
  await api.activateGoal(anna.id, first.id)
  await api.saveGoal(anna.id, { id: first.id, title: 'Курс', target: 12000 })
  self = (await api.workspace()).employees[0]
  assert.equal(self.goal.raised, 400); assert.equal(self.goal.title, 'Курс')
  assert.equal(self.goals[1].raised, 300)
  for (const scenario of ['declined', 'cancelled']) await api.pay({ qrId: qr.id, employeeId: anna.id, amount: 500, scenario })
  const controller = new AbortController()
  const request = api.pay({ qrId: qr.id, employeeId: anna.id, amount: 500, signal: controller.signal })
  controller.abort(); assert.equal((await request).status, 'cancelled')
  assert.equal((await api.workspace()).employees[0].goal.raised, 400)
})

test('deactivating an employee revokes login, session, goal editing and guest payment', async () => {
  const { anna, qr } = await restaurantFixture()
  await join(anna, 'anna@example.ru')
  await login('owner@example.ru'); await api.saveEmployee({ ...anna, active: false })
  await assert.rejects(login('anna@example.ru'), { code: 'UNAUTHORIZED' })
  const d = JSON.parse(values.get('tipro-demo-v1'))
  const u = d.users.find(u => u.email === 'anna@example.ru')
  d.session = { userId: u.id, employeeId: anna.id, merchantId: anna.merchantId, role: 'employee' }
  values.set('tipro-demo-v1', JSON.stringify(d))
  await assert.rejects(api.workspace(), { code: 'UNAUTHORIZED' })
  await assert.rejects(api.saveGoal(anna.id, { title: 'Цель', target: 1000 }), { code: 'UNAUTHORIZED' })
  assert.equal(await api.session(), null)
  assert.equal((await api.resolveQr(qr.id)).employees.some(e => e.id === anna.id), false)
  await assert.rejects(api.pay({ qrId: qr.id, employeeId: anna.id, amount: 300 }), { code: 'INVALID_EMPLOYEE' })
})

test('legacy accounts, employee goals, payments and old invitations migrate without data loss', async () => {
  values.set('tipro-demo-v1', JSON.stringify({ version: 3, merchants: [{ id: 'm1', name: 'Ресторан', email: 'demo@tipro.ru' }], employees: [{ id: 'e1', merchantId: 'm1', name: 'Анна', role: 'Официант', active: true, accessToken: 'old-invitation', goal: { id: 'g1', title: 'Мечта', raised: 300, target: 2000 } }], qrs: [{ id: 'q1', merchantId: 'm1', active: true }], payments: [{ id: 'p1', merchantId: 'm1', employeeId: 'e1', amount: 300, status: 'success' }], credentials: {}, session: { role: 'merchant', merchantId: 'm1' } }))
  assert.equal((await api.session()).role, 'merchant')
  assert.equal((await api.workspace()).payments.length, 1)
  await api.register({ role: 'employee', name: 'Анна', email: 'anna@example.ru', password, invite: 'old-invitation' })
  const workspace = await api.workspace()
  assert.equal(workspace.employees[0].goal.raised, 300)
  assert.equal(workspace.employees[0].goals.length, 1)
  assert.equal(workspace.payments.length, 1)
  await api.logout(); await api.login({ email: 'demo@tipro.ru', password: 'Demo12345' })
  assert.equal((await api.session()).role, 'merchant')
})

test('QR, goals, roles, employee membership and amounts validate inputs', async () => {
  const { anna, qr } = await restaurantFixture()
  await assert.rejects(api.resolveQr('missing'), { code: 'INVALID_QR' })
  await assert.rejects(api.resolveRestaurant('another', qr.id), { code: 'INVALID_QR' })
  await join(anna, 'anna@example.ru')
  for (const goal of [{ title: '', target: 1000 }, { title: 'Цель', target: -1 }, { title: 'Цель', target: 100.5 }]) await assert.rejects(api.saveGoal(anna.id, goal), { code: 'VALIDATION' })
  for (const amount of [0, 50001, NaN, 10.5]) await assert.rejects(api.pay({ qrId: qr.id, employeeId: anna.id, amount }), { code: 'VALIDATION' })
  await assert.rejects(api.pay({ qrId: qr.id, employeeId: 'foreign', amount: 300 }), { code: 'INVALID_EMPLOYEE' })
  await login('owner@example.ru'); await api.toggleQr(qr.id)
  await assert.rejects(api.resolveQr(qr.id), { code: 'INVALID_QR' })
})

test('merchant creates a receipt QR with a number and order total; receipt details are validated', async () => {
  await api.register({ role: 'merchant', name: 'Администратор', restaurantName: 'Ресторан', email: 'receipt@example.ru', password })
  const employee=await api.saveEmployee({ name: 'Анна', role: 'Официант' })
  assert.ok(employee.accessToken)
  assert.equal((await api.invitation(employee.accessToken)).name, 'Анна')
  const qr=await api.createQr({receiptNumber:'1042',billAmount:2800})
  assert.deepEqual(qr.receipt,{number:'1042',billAmount:2800})
  assert.equal(qr.label,'Чек № 1042')
  assert.ok(qr.createdAt)
  const page=await api.resolveRestaurant(qr.merchantId,qr.id)
  assert.equal(page.employees[0].id,employee.id)
  assert.equal(page.qr.receipt.billAmount,2800)
  for(const receipt of [{receiptNumber:'',billAmount:100},{receiptNumber:'1',billAmount:0},{receiptNumber:'1',billAmount:10.5},{receiptNumber:'1',billAmount:10000001}]) await assert.rejects(api.createQr(receipt),{code:'VALIDATION'})
})
