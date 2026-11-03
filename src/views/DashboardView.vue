<script setup>
import { computed, ref } from 'vue'
import { Wallet, ArrowRight, CheckCheck, UsersRound, ChartNoAxesCombined, Plus, CalendarDays } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { money, initials } from '../utils/format'
import StatCard from '../components/StatCard.vue'
import TipsChart from '../components/TipsChart.vue'
import PaymentTable from '../components/PaymentTable.vue'
const store=useAppStore(),days=ref(7)
const leaders=computed(()=>store.employees.map(e=>({...e,sum:store.successful.filter(p=>p.employeeId===e.id).reduce((s,p)=>s+p.amount,0)})).sort((a,b)=>b.sum-a.sum).slice(0,4))
</script>
<template>
  <div class="page-heading"><div><h1>{{ store.merchant?.name || 'Обзор ресторана' }}</h1><p>Статистика чаевых и команды за всё время</p></div><RouterLink to="/app/qr" class="btn btn-primary"><Plus :size="17"/>Создать QR-код</RouterLink></div>
  <div class="stats-grid"><StatCard label="Получено чаевых" :value="money(store.total)" note="Успешные платежи" :icon="Wallet"/><StatCard label="Успешные платежи" :value="store.successful.length" note="За всё время" :icon="CheckCheck"/><StatCard label="Средние чаевые" :value="money(store.average)" note="На один платёж" :icon="ChartNoAxesCombined"/><StatCard label="Сотрудники" :value="store.employees.filter(e=>e.active).length" :note="`${store.employees.length} в команде всего`" :icon="UsersRound"/></div>
  <template v-if="store.payments.length"><div class="overview-middle"><section class="panel"><div class="panel-heading"><div><h2>Динамика чаевых</h2><p>Сумма успешных платежей по дням</p></div><label class="select-compact"><CalendarDays :size="15"/><select v-model.number="days" aria-label="Период графика"><option :value="7">7 дней</option><option :value="14">14 дней</option><option :value="30">30 дней</option></select></label></div><TipsChart :payments="store.payments" :days="days"/></section><section class="panel"><div class="panel-heading"><h2>По сотрудникам</h2></div><div v-for="e in leaders" :key="e.id" class="leader"><span class="avatar small" :class="e.color">{{ initials(e.name) }}</span><div class="leader-name"><strong>{{ e.name }}</strong><span>{{ e.role }}</span></div><strong>{{ money(e.sum) }}</strong></div><RouterLink to="/app/employees" class="text-link leader-link">Вся команда<ArrowRight :size="15"/></RouterLink></section></div><section class="panel section-gap"><div class="panel-heading"><h2>Последние платежи</h2><RouterLink to="/app/payments" class="text-link">Все платежи<ArrowRight :size="15"/></RouterLink></div><PaymentTable :payments="store.sortedPayments.slice(0,5)" :employee-name="store.employeeName"/></section></template>
  <section v-else class="panel empty"><h3>Начните с команды</h3><p>Добавьте сотрудников, отправьте приглашения и разместите QR-код ресторана. Здесь появится статистика первых платежей.</p><RouterLink :to="store.employees.length?'/app/qr':'/app/employees'" class="btn btn-outline">{{ store.employees.length?'Создать QR-код':'Добавить сотрудника' }}</RouterLink></section>
</template>
