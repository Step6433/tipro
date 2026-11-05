// Exercise the exact Vue REST adapter against a running FastAPI/PostgreSQL stack.
// Uses optional demo data and never prints passwords or tokens.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createServer } from 'vite'
const base=process.env.TIPRO_API_URL || 'http://127.0.0.1:8000'
const contents=readFileSync(new URL('../backend/.env',import.meta.url),'utf8')
const password=process.env.DEMO_PASSWORD || contents.split('\n').find(line=>line.startsWith('DEMO_PASSWORD='))?.slice('DEMO_PASSWORD='.length).trim().replace(/^['"]|['"]$/g,'')
if(!password)throw new Error('Set DEMO_PASSWORD and run the backend seed first.')
const originalFetch=globalThis.fetch
let cookie=''
globalThis.fetch=async(input,options={})=>{
  const headers=new Headers(options.headers)
  if(cookie)headers.set('Cookie',cookie)
  const response=await originalFetch(new URL(input,base),{...options,headers})
  for(const value of response.headers.getSetCookie())if(value.startsWith('tipro_session='))cookie=value.split(';')[0]
  return response
}
const vite=await createServer({server:{middlewareMode:true},appType:'custom'})
try{
  const {restApi:api}=await vite.ssrLoadModule('/src/api/rest.js')
  await api.login({email:'manager1@tipro.example.com',password})
  const before=await api.workspace({currency:'THB'})
  assert.equal(before.user.role,'merchant')
  const employee=before.employees.find(e=>e.registered)
  assert.ok(employee,'A demo employee must exist; run the seed.')
  const qr=before.qrs.find(q=>q.active&&q.employeeId===employee.id) || await api.createQr({employeeId:employee.id,label:'Проверка оплаты',currency:before.currency})
  const totalBefore=before.analytics.totals[0].total
  await api.logout()
  await api.login({email:'worker11@tipro.example.com',password})
  const worker=await api.workspace({currency:'THB'})
  assert.equal(worker.employees.length,1)
  assert.equal(worker.employees[0].id,employee.id)
  await api.saveGoal(employee.id,{title:'Проверка сквозной оплаты',target:'50000',currency:'THB'})
  await api.logout()
  const page=await api.resolveRestaurant(qr.merchantId,qr.id)
  assert.equal(page.qr.currency,'THB')
  // Reproduce a phone opening a plain HTTP LAN address: randomUUID is absent.
  const cryptoDescriptor=Object.getOwnPropertyDescriptor(globalThis,'crypto')
  const browserCrypto=globalThis.crypto
  let payment
  try {
    Object.defineProperty(globalThis,'crypto',{configurable:true,value:{getRandomValues:browserCrypto.getRandomValues.bind(browserCrypto)}})
    assert.equal(globalThis.crypto.randomUUID,undefined)
    payment=await api.pay({qrId:qr.id,employeeId:employee.id,amount:'12.50',currency:'THB'})
  } finally {
    if(cryptoDescriptor)Object.defineProperty(globalThis,'crypto',cryptoDescriptor)
    else delete globalThis.crypto
  }
  assert.equal(payment.status,'success')
  await api.login({email:'worker11@tipro.example.com',password})
  const after=await api.workspace({currency:'THB'})
  assert.equal(after.employees[0].goal.raised,12.5)
  assert.ok(after.payments.every(p=>p.employeeId===employee.id&&p.currency==='THB'))
  assert.ok(after.payments.some(p=>p.id===payment.id))
  await api.logout();await api.login({email:'manager1@tipro.example.com',password})
  const manager=await api.workspace({currency:'THB'})
  assert.equal(manager.analytics.totals[0].total,totalBefore+12.5)
  const csv=await api.exportPayments({currency:'THB'})
  assert.ok((await csv.text()).includes('THB'))
  await api.logout()
  console.log('Vue REST adapter: login → restaurant QR → guest payment → PostgreSQL → employee goal → manager analytics → CSV: PASS')
}finally{globalThis.fetch=originalFetch;await vite.close()}
