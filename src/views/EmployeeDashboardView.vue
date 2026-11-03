<script setup>
import { Wallet, CheckCheck, ChartNoAxesCombined, ArrowRight } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { money } from '../utils/format'
import StatCard from '../components/StatCard.vue'
import TipsChart from '../components/TipsChart.vue'
import PaymentTable from '../components/PaymentTable.vue'
import GoalProgress from '../components/GoalProgress.vue'
const store=useAppStore()
</script>
<template>
  <div class="page-heading"><div><h1>Моя статистика</h1><p>{{ store.self?.name }} · {{ store.self?.role }} · {{ store.merchant?.name }}</p></div><RouterLink to="/app/goals" class="btn btn-outline">Мои цели<ArrowRight :size="16"/></RouterLink></div>
  <div class="stats-grid three"><StatCard label="Получено чаевых" :value="money(store.total)" note="За всё время" :icon="Wallet"/><StatCard label="Успешные платежи" :value="store.successful.length" note="Только ваши платежи" :icon="CheckCheck"/><StatCard label="Средние чаевые" :value="money(store.average)" note="На один успешный платёж" :icon="ChartNoAxesCombined"/></div>
  <div class="employee-overview"><section class="panel"><div class="panel-heading"><div><h2>Чаевые за неделю</h2><p>Успешные платежи за последние 7 дней</p></div></div><TipsChart v-if="store.successful.length" :payments="store.payments"/><div v-else class="empty"><h3>Платежей пока нет</h3><p>Ваши чаевые появятся здесь после оплаты гостем по QR-коду ресторана.</p></div></section><section class="panel active-goal-panel"><div class="panel-heading"><h2>Текущая цель</h2><RouterLink to="/app/goals" class="text-link">Все цели</RouterLink></div><GoalProgress v-if="store.self?.goal" :goal="store.self.goal"/><div v-else class="empty"><h3>На что копите?</h3><p>Добавьте цель — гости увидят её на странице ресторана.</p><RouterLink to="/app/goals" class="btn btn-outline">Добавить цель</RouterLink></div></section></div>
  <section class="panel section-gap"><div class="panel-heading"><h2>Последние платежи</h2><RouterLink to="/app/payments" class="text-link">Все платежи<ArrowRight :size="15"/></RouterLink></div><PaymentTable :payments="store.sortedPayments.slice(0,5)" :employee-name="store.employeeName"/></section>
</template>
