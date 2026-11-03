<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { X } from 'lucide-vue-next'
defineProps({ title: String, subtitle: String })
const emit = defineEmits(['close'])
const panel = ref(null)
let previousFocus
function key(event) {
  if (event.key === 'Escape') emit('close')
  if (event.key === 'Tab') {
    const elements = [...panel.value.querySelectorAll('button,input,select,a[href]')].filter(e => !e.disabled)
    const first = elements[0], last = elements.at(-1)
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }
}
onMounted(async () => { previousFocus = document.activeElement; document.body.style.overflow = 'hidden'; document.addEventListener('keydown', key); await nextTick(); panel.value.querySelector('input,select,button')?.focus() })
onUnmounted(() => { document.body.style.overflow = ''; document.removeEventListener('keydown', key); previousFocus?.focus() })
</script>
<template><Teleport to="body"><div class="modal-backdrop" @click.self="emit('close')"><section ref="panel" class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button class="icon-btn modal-close" @click="emit('close')" aria-label="Закрыть"><X :size="20" /></button><h2 id="modal-title">{{ title }}</h2><p class="muted" v-if="subtitle">{{ subtitle }}</p><slot /></section></div></Teleport></template>
