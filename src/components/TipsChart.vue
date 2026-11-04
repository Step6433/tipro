<script setup>
import { computed, ref } from 'vue'
import { locale, numberLocales } from '../i18n'
import { money, localDate } from '../utils/format'
const props = defineProps({ payments: Array, dailySeries: {type:Array,default:null}, days: { type: Number, default: 7 } })
const hovered = ref(null)
const series = computed(() => Array.from({ length: props.days }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - props.days + 1 + i); const key = localDate(d); return { date: d.toLocaleDateString(numberLocales[locale.value], { day: 'numeric', month: 'short' }), value: props.dailySeries ? Number(props.dailySeries.find(s=>s.period.slice(0,10)===d.toISOString().slice(0,10))?.total||0) : props.payments.filter(p => p.status === 'success' && localDate(p.createdAt) === key).reduce((s,p) => s+p.amount,0) } }))
const max = computed(() => Math.max(1000, Math.ceil(Math.max(...series.value.map(s=>s.value)) / 1000) * 1000))
const points = computed(() => series.value.map((s,i) => ({ x: 20+i*(760/(props.days-1)), y: 170-s.value/max.value*145, ...s })))
const line = computed(() => points.value.map((p,i) => `${i?'L':'M'}${p.x},${p.y}`).join(' '))
const fill = computed(() => `${line.value} L780,180 L20,180 Z`)
const active = computed(() => hovered.value === null ? null : points.value[hovered.value])
</script>
<template><div class="chart"><div class="chart-y"><span>{{ money(max) }}</span><span>{{ money(max/2) }}</span><span>{{ money(0) }}</span></div><div class="chart-canvas"><svg viewBox="0 0 800 200" role="img" :aria-label="$t('Чаевые за {0} дней', {0: days})"><defs><linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#2c9570" stop-opacity=".17"/><stop offset="100%" stop-color="#2c9570" stop-opacity="0"/></linearGradient></defs><path d="M0 25H800 M0 97H800 M0 170H800" stroke="#e9ece7" stroke-dasharray="4 5"/><path :d="fill" fill="url(#chartFill)"/><path :d="line" fill="none" stroke="#258563" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><g v-for="(p,i) in points" :key="i" @mouseenter="hovered=i" @mouseleave="hovered=null"><rect :x="p.x-12" y="0" width="24" height="190" fill="transparent"/><circle :cx="p.x" :cy="p.y" :r="hovered===i?5:3" fill="#fff" stroke="#258563" stroke-width="2"/><title>{{ p.date }}: {{ money(p.value) }}</title></g><g v-if="active"><rect :x="Math.min(660, Math.max(0, active.x-60))" :y="Math.max(0,active.y-39)" width="120" height="27" rx="7" fill="#174e3b"/><text :x="Math.min(720,Math.max(60,active.x))" :y="Math.max(18,active.y-21)" text-anchor="middle" fill="white" font-size="12">{{ money(active.value) }}</text></g></svg><div class="chart-x"><span v-for="(s,i) in series" :key="i" v-show="days <= 7 || i%5===0 || i===days-1">{{ s.date }}</span></div></div></div></template>
