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
  <div class="page-heading"><div><h1>{{ $t('Моя статистика') }}</h1><p>{{ store.self?.name }} · {{ $t(store.self?.role) }} · {{ store.merchant?.name }}</p></div><RouterLink to="/app/goals" class="btn btn-outline">{{ $t('Мои цели') }}<ArrowRight :size="16"/></RouterLink></div>
  <div class="stats-grid three"><StatCard :label="$t('Получено чаевых')" :value="money(store.total)" :note="$t('За всё время')" :icon="Wallet"/><StatCard :label="$t('Успешные платежи')" :value="store.successful.length" :note="$t('Только ваши платежи')" :icon="CheckCheck"/><StatCard :label="$t('Средние чаевые')" :value="money(store.average)" :note="$t('На один успешный платёж')" :icon="ChartNoAxesCombined"/></div>
  <div class="employee-overview"><section class="panel"><div class="panel-heading"><div><h2>{{ $t('Чаевые за неделю') }}</h2><p>{{ $t('Успешные платежи за последние 7 дней') }}</p></div></div><TipsChart v-if="store.successful.length" :payments="store.payments" :daily-series="store.analytics?.series" :series-time-zone="store.analytics?.timezone"/><div v-else class="empty"><h3>{{ $t('Платежей пока нет') }}</h3><p>{{ $t('Ваши чаевые появятся здесь после оплаты гостем по QR-коду ресторана.') }}</p></div></section><section class="panel active-goal-panel"><div class="panel-heading"><h2>{{ $t('Текущая цель') }}</h2><RouterLink to="/app/goals" class="text-link">{{ $t('Все цели') }}</RouterLink></div><GoalProgress v-if="store.self?.goal" :goal="store.self.goal"/><div v-else class="empty"><h3>{{ $t('На что копите?') }}</h3><p>{{ $t('Добавьте цель — гости увидят её на странице ресторана.') }}</p><RouterLink to="/app/goals" class="btn btn-outline">{{ $t('Добавить цель') }}</RouterLink></div></section></div>
  <section class="panel section-gap"><div class="panel-heading"><h2>{{ $t('Последние платежи') }}</h2><RouterLink to="/app/payments" class="text-link">{{ $t('Все платежи') }}<ArrowRight :size="15"/></RouterLink></div><PaymentTable :payments="store.sortedPayments.slice(0,5)" :employee-name="store.employeeName"/></section>
</template>
