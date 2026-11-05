import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createPinia, setActivePinia } from 'pinia'
import { createSSRApp, h } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import { renderToString } from '@vue/server-renderer'
const vite=await createServer({server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'})
after(()=>vite.close())
const {useAppStore}=await vite.ssrLoadModule('/src/stores/app.js')
const {setAccessToken}=await vite.ssrLoadModule('/src/api/http.js')
const i18n=await vite.ssrLoadModule('/src/i18n/index.js')

test('pending merchant receives a waiting session without loading protected workspace',async()=>{
  const original=globalThis.fetch,seen=[]
  let status='PENDING'
  const session=()=>({userId:'1',merchantId:'2',role:'merchant',merchantStatus:status,merchantName:'Test restaurant'})
  globalThis.fetch=async(input)=>{
    const url=new URL(input,'http://localhost'),path=url.pathname;seen.push(path)
    let data
    if(path==='/api/auth/register')data={accessToken:'test-session',session:session()}
    else if(path==='/api/auth/me')data={session:session()}
    else if(path==='/api/workspace')data={user:{...session(),name:'Owner'},merchant:{id:'2',currency:'RUB'}}
    else if(['/api/employees','/api/qrs','/api/payments'].includes(path))data={items:[],total:0}
    else if(path==='/api/analytics')data={totals:[],series:[],byEmployee:[]}
    else throw new Error('Unexpected request '+path)
    return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}})
  }
  try{
    setActivePinia(createPinia())
    const store=useAppStore()
    await store.authenticate('register',{role:'merchant',name:'Owner',email:'owner@example.com',password:'Test-only-password',restaurantName:'Test restaurant'})
    assert.equal(store.awaitingApproval,true)
    await store.refreshSession()
    assert.ok(!seen.includes('/api/workspace'))
    status='ACTIVE'
    await store.refreshSession()
    assert.equal(store.awaitingApproval,false)
    assert.ok(seen.includes('/api/workspace'))
    assert.equal(store.merchant.id,'2')
  }finally{globalThis.fetch=original;setAccessToken(null)}
})

test('waiting page explains platform approval in all interface languages',async()=>{
  const {default:Approval}=await vite.ssrLoadModule('/src/views/ApprovalView.vue')
  for(const [locale,heading] of [['ru','Ресторан ожидает подтверждения'],['en','Restaurant awaiting approval'],['zh','餐厅等待审核']]){
    const pinia=createPinia();setActivePinia(pinia)
    const store=useAppStore();store.session={role:'merchant',merchantStatus:'PENDING',merchantName:'Test restaurant'}
    const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>h('div')}}]})
    i18n.setLocale(locale,false)
    const app=createSSRApp(Approval).use(pinia).use(router).use(i18n.default)
    const html=await renderToString(app)
    assert.ok(html.includes(heading))
    assert.ok(html.includes('Test restaurant'))
    assert.ok(!html.includes('/app/qr'))
  }
})
