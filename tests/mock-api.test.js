import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { mockApi as api } from '../src/api/mock.js'
let values
beforeEach(() => { values=new Map(); globalThis.localStorage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)} })
async function fixture(type = 'receipt') {
 await api.demo()
 await api.saveEmployee({name:'Тест Официант',role:'Официант'})
 const employee=(await api.workspace()).employees[0]
 const qr=await api.createQr({employeeId:employee.id,type,bill:2000})
 return {employee,qr}
}
test('fresh account has no employees, QR codes, payments or other restaurants',async()=>{
 await api.demo('admin')
 const workspace=await api.workspace()
 assert.deepEqual(workspace.employees,[])
 assert.deepEqual(workspace.qrs,[])
 assert.deepEqual(workspace.payments,[])
 assert.equal((await api.admin()).merchants.length,1)
})
test('old demo data is cleared once; accounts and subsequent new data persist',async()=>{
 values.set('tipro-demo-v1',JSON.stringify({version:1,merchants:[{id:'m1',name:'Ресторан'},{id:'m2'},{id:'m3'},{id:'custom',name:'Мой ресторан'}],employees:[{id:'e1'}],qrs:[{id:'anna'}],payments:[{id:'tx1'}],credentials:{custom:'hash'},session:{merchantId:'m1',role:'admin'}}))
 const workspace=await api.workspace()
 assert.deepEqual(workspace.employees,[]);assert.deepEqual(workspace.qrs,[]);assert.deepEqual(workspace.payments,[])
 assert.equal((await api.admin()).merchants.length,2)
 assert.equal(JSON.parse(values.get('tipro-demo-v1')).credentials.custom,'hash')
 await api.saveEmployee({name:'Новый сотрудник',role:'Официант'})
 assert.equal((await api.workspace()).employees.length,1)
 assert.equal((await api.session()).role,'admin')
})
test('registration → employee → one-time QR → successful payment → history and totals',async()=>{
 await api.register({name:'Тестовый ресторан',email:'new@example.ru',password:'Test12345'})
 assert.equal((await api.workspace()).employees.length,0)
 await api.saveEmployee({name:'Тест Официант',role:'Официант'})
 const before=await api.workspace(),e=before.employees[0]
 const q=await api.createQr({employeeId:e.id,type:'receipt',bill:2000,label:'Чек № 1'})
 assert.equal((await api.resolveQr(q.id)).employee.id,e.id)
 const p=await api.pay({qrId:q.id,amount:300})
 const after=await api.workspace()
 assert.equal(p.status,'success'); assert.equal(after.payments.length,1)
 assert.equal(after.payments.reduce((s,p)=>s+p.amount,0),300)
 await assert.rejects(api.resolveQr(q.id),{code:'USED_QR'})
 await assert.rejects(api.pay({qrId:q.id,amount:300}),{code:'USED_QR'})
 await api.logout(); await api.login({email:'new@example.ru',password:'Test12345'})
 assert.equal((await api.workspace()).employees[0].id,e.id)
})
test('declined and cancelled payments are recorded and do not consume a receipt QR',async()=>{
 const {qr}=await fixture();const before=await api.workspace()
 for(const scenario of ['declined','cancelled']) { const p=await api.pay({qrId:qr.id,amount:150,scenario});assert.equal(p.status,scenario);await api.resolveQr(qr.id) }
 const after=await api.workspace(); assert.equal(after.payments.length,before.payments.length+2)
 assert.equal(after.payments.filter(p=>p.status==='success').length,before.payments.filter(p=>p.status==='success').length)
})
test('cancelling an in-flight request records cancellation',async()=>{
 const {qr}=await fixture();const controller=new AbortController();const promise=api.pay({qrId:qr.id,amount:300,signal:controller.signal});controller.abort();assert.equal((await promise).status,'cancelled');await api.resolveQr(qr.id)
})
test('invalid, used and disabled employee QR codes are rejected',async()=>{
 await assert.rejects(api.resolveQr('missing'),{code:'INVALID_QR'})
 const {qr,employee:e}=await fixture('personal')
 const used=await api.createQr({employeeId:e.id,type:'receipt',bill:2000})
 await api.pay({qrId:used.id,amount:150})
 await assert.rejects(api.resolveQr(used.id),{code:'USED_QR'})
 await api.saveEmployee({...e,active:false});await assert.rejects(api.resolveQr(qr.id),{code:'INVALID_QR'})
 await api.saveEmployee({...e,name:'Анна Новая',active:true});assert.equal((await api.resolveQr(qr.id)).employee.name,'Анна Новая')
 await api.toggleQr(qr.id);await assert.rejects(api.resolveQr(qr.id),{code:'INVALID_QR'})
})
test('personal QR allows multiple payments; invalid amounts are rejected',async()=>{
 const {qr}=await fixture('personal')
 for(let i=0;i<2;i++) assert.equal((await api.pay({qrId:qr.id,amount:150})).status,'success')
 for(const amount of [0,-1,50001,NaN,10.5]) await assert.rejects(api.pay({qrId:qr.id,amount}),{code:'VALIDATION'})
})
test('authentication, merchant isolation and admin scope',async()=>{
 await assert.rejects(api.workspace(),{code:'UNAUTHORIZED'})
 await assert.rejects(api.saveEmployee({name:'Нет доступа',role:'Официант'}),{code:'UNAUTHORIZED'})
 await assert.rejects(api.login({email:'demo@tipro.ru',password:'wrong'}))
 const {qr}=await fixture();await assert.rejects(api.admin(),{code:'UNAUTHORIZED'})
 await api.register({name:'Второй',email:'second@example.ru',password:'Test12345'})
 await assert.rejects(api.toggleQr(qr.id),{code:'UNAUTHORIZED'})
 await assert.rejects(api.register({name:'Дубликат',email:'second@example.ru',password:'Test12345'}))
 await api.demo('admin');assert.equal((await api.admin()).merchants.length,2)
})
