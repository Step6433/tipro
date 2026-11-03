import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore } from '../stores/app'
const router = createRouter({ history: createWebHistory(), scrollBehavior: () => ({ top: 0 }), routes: [
  { path: '/', component: () => import('../views/HomeView.vue'), meta: { title: 'Онлайн-чаевые' } },
  { path: '/login', component: () => import('../views/AuthView.vue'), meta: { title: 'Вход' } },
  { path: '/register', component: () => import('../views/AuthView.vue'), meta: { title: 'Регистрация' } },
  { path: '/pay/:id', component: () => import('../views/PayView.vue'), meta: { title: 'Оставить чаевые' } },
  { path: '/app', component: () => import('../layouts/DashboardLayout.vue'), meta: { auth: true }, children: [
    { path: '', component: () => import('../views/DashboardView.vue'), meta: { title: 'Обзор' } },
    { path: 'employees', component: () => import('../views/EmployeesView.vue'), meta: { title: 'Команда' } },
    { path: 'qr', component: () => import('../views/QrView.vue'), meta: { title: 'QR-коды' } },
    { path: 'payments', component: () => import('../views/PaymentsView.vue'), meta: { title: 'История платежей' } },
    { path: 'admin', component: () => import('../views/AdminView.vue'), meta: { title: 'Администрирование', admin: true } },
  ] },
  { path: '/:pathMatch(.*)*', component: () => import('../views/NotFoundView.vue'), meta: { title: 'Страница не найдена' } },
] })
router.beforeEach(async to => {
  const store = useAppStore()
  try { await store.init() } catch { return to.meta.auth ? '/login' : true }
  if (to.meta.auth && !store.session) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.admin && store.session?.role !== 'admin') return '/app'
})
router.afterEach(to => { document.title = `${to.meta.title || 'Tipro'} · Tipro` })
export default router
