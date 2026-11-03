<script setup>
import { ArrowUpRight } from 'lucide-vue-next'
defineProps({ label: String, value: [String, Number], note: String, icon: Object, accent: Boolean })
</script>
<template><div class="stat-card" :class="{ 'stat-accent': accent }"><div class="stat-top"><span>{{ label }}</span><component :is="icon" :size="19" /></div><div class="stat-value">{{ value }}</div><div class="stat-note"><ArrowUpRight v-if="accent" :size="14" />{{ note }}</div></div></template>
