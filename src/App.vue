<script setup>
import { useAppStore } from './stores/app'
import { CheckCircle2 } from 'lucide-vue-next'
const store = useAppStore()
</script>
<template><RouterView /><Transition name="toast"><div v-if="store.toast" class="toast" role="status"><CheckCircle2 :size="19" />{{ $t(store.toast) }}</div></Transition></template>
