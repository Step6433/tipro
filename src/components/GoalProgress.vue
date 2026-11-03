<script setup>
import { computed } from 'vue'
import { money } from '../utils/format'
const props = defineProps({ goal: Object })
const percent = computed(() => props.goal ? Math.min(100, Math.round(props.goal.raised / props.goal.target * 100)) : 0)
</script>
<template><div v-if="goal" class="dream-goal"><div class="dream-label">Цель<span>{{ percent }}%</span></div><strong>{{ goal.title }}</strong><progress :value="Math.min(goal.raised,goal.target)" :max="goal.target" :aria-label="`На мечту: ${goal.title}`"></progress><div class="dream-amounts"><span>{{ money(goal.raised) }} собрано</span><span>из {{ money(goal.target) }}</span></div><p v-if="goal.raised>=goal.target" class="dream-complete">Цель достигнута</p></div></template>
