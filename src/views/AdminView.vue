<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Store, Wallet, UsersRound, ArrowUpRight, ShieldCheck, Bell, Check } from 'lucide-vue-next'
import { api } from '../api'
import { useAppStore } from '../stores/app'
const store=useAppStore()
import { money, initials } from '../utils/format'
import StatCard from '../components/StatCard.vue'
import PaymentTable from '../components/PaymentTable.vue'
const data=ref(null),error=ref(''),loading=ref(true),selected=ref(''), limit=ref(12)
const approving=ref(''),approvalError=ref('')
let poll, running=false
async function load(silent=false){
  if(running)return
  running=true
  if(!silent)loading.value=true
  error.value=''
  try{data.value=await api.admin({currency:store.currency});store.pendingRestaurantCount=data.value.notifications.length}
  catch(e){error.value=e.message}
  finally{loading.value=false;running=false}
}
async function approve(restaurant){
  if(approving.value)return
  approving.value=restaurant.id;approvalError.value=''
  try{await api.approveRestaurant(restaurant.id);store.notify('Ресторан подтверждён');await load(true)}
  catch(e){approvalError.value=e.message}
  finally{approving.value=''}
}
onMounted(()=>{load();poll=window.setInterval(()=>{if(document.visibilityState==='visible')load(true)},10000)})
onUnmounted(()=>clearInterval(poll))
watch(()=>store.currency,()=>{selected.value='';load()})
const total=computed(()=>data.value?.analytics.totals.find(t=>t.currency===store.currency)?.total||0)
const employees=computed(()=>data.value?.employees.filter(e=>!selected.value||e.merchantId===selected.value)||[])
const payments=computed(()=>[...(data.value?.payments||[])].filter(p=>!selected.value||p.merchantId===selected.value).sort((a,b)=>new Date(b.createdAt)-new Date(a.createdAt)))
const name=id=>data.value?.employees.find(e=>e.id===id)?.name||'Сотрудник'
</script>
<template><div class="page-heading"><div><h1>{{ $t('Обзор платформы') }}</h1><p>{{ $t('Статистика всех ресторанов, сотрудников и платежей.') }}</p></div><span class="demo-pill"><ShieldCheck :size="15"/>{{ $t('Администратор платформы') }}</span></div><div v-if="loading" class="page-loading"><span class="spinner"></span>{{ $t('Загрузка платформы…') }}</div><div v-else-if="error" class="error-banner">{{ $t(error) }}<button class="btn" @click="load">{{ $t('Повторить') }}</button></div><template v-else-if="data"><section class="panel approval-requests" aria-live="polite"><div class="panel-heading"><div><h2><Bell :size="18"/>{{ $t('Заявки ресторанов') }} <span class="notification-count">{{ data.notifications.length }}</span></h2><p>{{ $t('Новые рестораны не могут работать до вашего подтверждения.') }}</p></div><button class="text-link" @click="load(true)">{{ $t('Обновить') }}</button></div><p v-if="approvalError" class="error-text" role="alert">{{ $t(approvalError) }}</p><p v-if="!data.notifications.length" class="muted">{{ $t('Новых заявок нет') }}</p><article v-for="item in data.notifications" :key="item.id" class="approval-request"><div><strong>{{ item.restaurant.name }}</strong><p>{{ item.restaurant.email }}</p><small class="muted">{{ $t('Ожидает подтверждения') }}</small></div><button class="btn btn-primary btn-small" :disabled="!!approving" @click="approve(item.restaurant)"><Check :size="16"/>{{ approving===item.restaurant.id?$t('Подтверждаем…'):$t('Подтвердить ресторан') }}</button></article></section><div class="stats-grid admin-stats"><StatCard :label="$t('Рестораны')" :value="data.merchants.length" :note="$t('Зарегистрированы на платформе')" :icon="Store"/><StatCard :label="$t('Чаевые платформы')" :value="money(total)" :note="$t('Успешные платежи за всё время')" :icon="Wallet" accent/><StatCard :label="$t('Сотрудники')" :value="data.employees.length" :note="$t('Сотрудники всех ресторанов')" :icon="UsersRound"/></div><section class="panel"><div class="panel-heading"><div><h2>{{ $t('Рестораны') }}</h2><p>{{ $t('Выберите ресторан, чтобы посмотреть его данные') }}</p></div><button class="text-link" @click="selected=''">{{ $t('Вся платформа') }}</button></div><div class="merchant-list"><button v-for="m in data.merchants" :key="m.id" :class="{selected:selected===m.id}" @click="selected=m.id"><span class="avatar sage">{{ initials(m.name) }}</span><span><strong>{{ m.name }}</strong><small>{{ m.email }}</small></span><span class="merchant-location">{{ m.location }}</span><ArrowUpRight :size="19"/></button></div></section><div class="admin-details"><section class="panel"><div class="panel-heading"><h2>{{ $t('Сотрудники') }} <span class="muted">{{ employees.length }}</span></h2></div><div v-if="!employees.length" class="empty">{{ $t('Сотрудники пока не добавлены') }}</div><div v-for="e in employees" :key="e.id" class="admin-employee"><span class="avatar small" :class="e.color">{{ initials(e.name) }}</span><div><strong>{{ e.name }}</strong><small>{{ $t(e.role) }}</small></div><span class="status" :class="e.active?'success':'cancelled'">{{ e.active?$t('Активен'):$t('Неактивен') }}</span></div></section><section class="panel"><div class="panel-heading"><h2>{{ $t('Платежи') }} <span class="muted">{{ payments.length }}</span></h2></div><PaymentTable :payments="payments.slice(0,limit)" :employee-name="name"/><div v-if="payments.length>limit" class="pagination"><span>{{ $t('Показано') }} {{ limit }} {{ $t('из') }} {{ payments.length }}</span><button class="text-link" @click="limit+=12">{{ $t('Показать ещё') }}</button></div></section></div></template></template>
