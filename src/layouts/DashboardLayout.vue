<script setup>
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LayoutDashboard, UsersRound, QrCode, ArrowLeftRight, ShieldCheck, LogOut, Menu, X, Target, Settings } from 'lucide-vue-next'
import BrandLogo from '../components/BrandLogo.vue'
import { useAppStore } from '../stores/app'
import { initials } from '../utils/format'
import { roleNames, homeForRole } from '../utils/roles'
const store=useAppStore(),route=useRoute(),router=useRouter(),mobile=ref(false)
const links=computed(()=>store.session?.role==='employee'?[
  {to:'/app/me',label:'Моя статистика',icon:LayoutDashboard},{to:'/app/goals',label:'Мои цели',icon:Target},{to:'/app/payments',label:'Мои платежи',icon:ArrowLeftRight},
]:store.session?.role==='admin'?[
  {to:'/app/admin',label:'Платформа',icon:ShieldCheck},
]:[
  {to:'/app',label:'Обзор',icon:LayoutDashboard},{to:'/app/employees',label:'Команда',icon:UsersRound},{to:'/app/qr',label:'QR-код',icon:QrCode},{to:'/app/payments',label:'Платежи',icon:ArrowLeftRight},{to:'/app/settings',label:'Настройки',icon:Settings},
])
async function refresh(){
  try{
    await store.refreshSession()
    if(!store.session){router.replace('/login');return}
    if(route.meta.roles&&!route.meta.roles.includes(store.session.role))router.replace(homeForRole(store.session.role))
  }catch{/* The store displays the loading error and retry control. */}
}
let refreshTimer
onMounted(()=>{
  if(!store.user)refresh()
  window.addEventListener('focus',refresh);window.addEventListener('storage',refresh)
  refreshTimer=window.setInterval(()=>{
    if(document.visibilityState==='visible'&&!store.loading&&store.session?.role!=='admin')refresh()
  },5000)
})
onUnmounted(()=>{clearInterval(refreshTimer);window.removeEventListener('focus',refresh);window.removeEventListener('storage',refresh)})
async function logout(){await store.logout();router.push('/login')}
</script>
<template>
  <div class="dashboard-shell">
    <button v-if="mobile" class="sidebar-overlay" @click="mobile=false" :aria-label="$t('Закрыть меню')"></button>
    <aside class="sidebar" :class="{open:mobile}">
      <div class="sidebar-brand"><BrandLogo/><button class="icon-btn mobile-only" @click="mobile=false" :aria-label="$t('Закрыть меню')"><X :size="20"/></button></div>
      <div class="workspace"><span class="workspace-icon">{{ initials(store.merchant?.name || 'Tipro') }}</span><div><strong>{{ store.merchant?.name || 'Tipro' }}</strong><span>{{ $t(roleNames[store.session?.role]) }}</span></div></div>
      <nav><RouterLink v-for="link in links" :key="link.to" :to="link.to" :class="{active:route.path===link.to}" @click="mobile=false"><component :is="link.icon" :size="18"/>{{ $t(link.label) }}</RouterLink></nav>
      <div class="sidebar-bottom"><div class="sidebar-profile"><span class="avatar small">{{ initials(store.user?.name) }}</span><div><strong>{{ store.user?.name }}</strong><span>{{ store.user?.email }}</span></div></div><button class="sidebar-utility" @click="logout"><LogOut :size="17"/>{{ $t('Выйти из аккаунта') }}</button></div>
    </aside>
    <div class="dashboard-body">
      <header class="topbar"><div class="breadcrumb"><button class="icon-btn mobile-only" @click="mobile=true" :aria-label="$t('Открыть меню')"><Menu :size="21"/></button><span>{{ $t(route.meta.title) }}</span></div><LanguageSwitcher/><span class="role-chip">{{ $t(roleNames[store.session?.role]) }}</span></header>
      <main class="dashboard-content"><div v-if="store.error" class="error-banner" role="alert">{{ $t(store.error) }}<button class="btn btn-outline btn-small" @click="refresh">{{ $t('Повторить') }}</button></div><div v-if="store.loading&&!store.user" class="page-loading"><span class="spinner"></span>{{ $t('Загрузка…') }}</div><RouterView v-else/></main>
      <footer class="dashboard-footer"><span>Tipro</span><span>{{ $t('Демонстрационная оплата · без реальных списаний') }}</span></footer>
    </div>
  </div>
</template>
