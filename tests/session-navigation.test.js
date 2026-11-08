import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createPinia, setActivePinia } from 'pinia'
import { createSSRApp, h } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import { renderToString } from '@vue/server-renderer'

const vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
after(() => vite.close())
const { useAppStore } = await vite.ssrLoadModule('/src/stores/app.js')
const { checkNavigation } = await vite.ssrLoadModule('/src/router/guard.js')
const { default: Home } = await vite.ssrLoadModule('/src/views/HomeView.vue')
const { setAccessToken } = await vite.ssrLoadModule('/src/api/http.js')
const i18n = await vite.ssrLoadModule('/src/i18n/index.js')

for (const [role, status, dashboard] of [
  ['merchant', 'ACTIVE', '/app'], ['employee', 'ACTIVE', '/app/me'],
  ['admin', null, '/app/admin'], ['merchant', 'PENDING', '/approval'],
]) {
  test(`${role}/${status}: dashboard → public home → dashboard preserves login, including a reload`, async () => {
    const originalFetch = globalThis.fetch, requests = []
    let signedIn = false
    const session = { userId: '7', role, merchantStatus: status, merchantId: role === 'admin' ? null : '3', employeeId: role === 'employee' ? '7' : null }
    globalThis.fetch = async (input) => {
      const path = new URL(input, 'http://localhost').pathname
      requests.push(path)
      let data
      if (path === '/api/auth/login') { signedIn = true; data = { accessToken: 'test-only-token', session } }
      else if (path === '/api/auth/me') {
        if (!signedIn) return new Response(JSON.stringify({ code: 'UNAUTHORIZED' }), { status: 401 })
        data = { session }
      } else if (path === '/api/auth/logout') { signedIn = false; return new Response(null, { status: 204 }) }
      else if (path === '/api/workspace') data = { user: { ...session, name: 'User' }, merchant: role === 'admin' ? null : { id: '3', currency: 'RUB' } }
      else if (['/api/employees', '/api/payments', '/api/qrs'].includes(path)) data = { items: [], total: 0 }
      else if (path === '/api/analytics') data = { totals: [], series: [], byEmployee: [] }
      else throw new Error(`Unexpected request: ${path}`)
      return new Response(JSON.stringify(data))
    }
    function setup() {
      const pinia = createPinia(); setActivePinia(pinia)
      const store = useAppStore()
      const router = createRouter({ history: createMemoryHistory(), routes: [
        { path: '/', component: Home },
        { path: dashboard, component: { render: () => h('div') }, meta: { auth: true, roles: [role] } },
        { path: '/login', component: { render: () => h('div') } },
        { path: '/register', component: { render: () => h('div') } },
      ] })
      router.beforeEach(to => checkNavigation(to, store))
      return { store, router, pinia }
    }
    async function renderHome({ router, pinia }) {
      i18n.setLocale('ru', false)
      const html = await renderToString(createSSRApp(Home).use(pinia).use(router).use(i18n.default))
      assert.ok(html.includes('Вернуться в кабинет'))
      assert.ok(html.includes(`href="${dashboard}"`))
      assert.ok(!html.includes('href="/login"'))
      assert.ok(!html.includes('href="/register"'))
    }
    try {
      const first = setup()
      await first.store.authenticate('login', { email: 'user@example.com', password: 'test-only-password' })
      assert.equal(first.store.ready, true)
      const reads = requests.filter(p => p === '/api/auth/me').length
      await first.router.push('/')
      assert.equal(requests.filter(p => p === '/api/auth/me').length, reads, 'Home should retain the just-established login')
      await renderHome(first)
      await first.router.push(dashboard)
      await first.router.push('/')
      assert.deepEqual(first.store.session, session)
      assert.ok(!requests.includes('/api/auth/logout'))
      await renderHome(first)
      // Simulate a page reload: fresh Pinia and no in-memory bearer; the server cookie remains.
      setAccessToken(null)
      const reloaded = setup()
      await reloaded.router.push('/')
      assert.deepEqual(reloaded.store.session, session)
      await renderHome(reloaded)
      await reloaded.router.push(dashboard)
      assert.equal(reloaded.router.currentRoute.value.path, dashboard)
      // Only an explicit logout should make the home page show sign-in again.
      await reloaded.store.logout()
      await reloaded.router.push('/')
      const html = await renderToString(createSSRApp(Home).use(reloaded.pinia).use(reloaded.router).use(i18n.default))
      assert.ok(html.includes('href="/login"'))
      assert.equal(reloaded.store.session, null)
      assert.equal(requests.filter(p => p === '/api/auth/logout').length, 1)
    } finally { globalThis.fetch = originalFetch; setAccessToken(null) }
  })
}
