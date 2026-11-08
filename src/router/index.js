import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore } from '../stores/app'
import { watch } from 'vue'
import { locale, t } from '../i18n'
import { checkNavigation } from './guard'
const router = createRouter({ history: createWebHistory(), scrollBehavior: () => ({ top: 0 }), routes: [
  { path: '/', component: () => import('../views/HomeView.vue'), meta: { title: 'Чаевые для команды' } },
  { path: '/login', component: () => import('../views/AuthView.vue'), meta: { title: 'Вход' } },
  { path: '/register', component: () => import('../views/AuthView.vue'), meta: { title: 'Регистрация' } },
  { path: '/approval', component: () => import('../views/ApprovalView.vue'), meta: { auth: true, title: 'Подтверждение ресторана', roles: ['merchant'] } },
  { path: '/employee/:token', redirect: to => ({ path: '/register', query: { role: 'employee', invite: to.params.token } }) },
  { path: '/restaurant/:merchantId', component: () => import('../views/PayView.vue'), meta: { title: 'Чаевые ресторану' } },
  { path: '/pay/:id', component: () => import('../views/PayView.vue'), meta: { title: 'Оставить чаевые' } },
  { path: '/app', component: () => import('../layouts/DashboardLayout.vue'), meta: { auth: true }, children: [
    { path: '', component: () => import('../views/DashboardView.vue'), meta: { title: 'Обзор ресторана', roles: ['merchant'] } },
    { path: 'employees', component: () => import('../views/EmployeesView.vue'), meta: { title: 'Команда', roles: ['merchant'] } },
    { path: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: 'Настройки ресторана', roles: ['merchant'] } },
    { path: 'qr', component: () => import('../views/QrView.vue'), meta: { title: 'QR-коды сотрудников', roles: ['merchant'] } },
    { path: 'payments', component: () => import('../views/PaymentsView.vue'), meta: { title: 'Платежи', roles: ['merchant', 'employee'] } },
    { path: 'me', component: () => import('../views/EmployeeDashboardView.vue'), meta: { title: 'Моя статистика', roles: ['employee'] } },
    { path: 'goals', component: () => import('../views/GoalsView.vue'), meta: { title: 'Мои цели', roles: ['employee'] } },
    { path: 'admin', component: () => import('../views/AdminView.vue'), meta: { title: 'Платформа', roles: ['admin'] } },
  ] },
  { path: '/:pathMatch(.*)*', component: () => import('../views/NotFoundView.vue'), meta: { title: 'Страница не найдена' } },
] })
router.beforeEach(to => checkNavigation(to, useAppStore()))
function updateTitle() { document.title = `${t(router.currentRoute.value.meta.title || 'Tipro')} · Tipro` }
router.afterEach(updateTitle)
watch(locale, updateTitle)
export default router
