<script setup>
import { ref, watch } from 'vue'
import QRCode from 'qrcode'
import { Copy, Download, ArrowUpRight, Link2, Power } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
const props=defineProps({qr:Object,employeeName:String})
const emit=defineEmits(['toggle'])
const store=useAppStore(), image=ref(''), error=ref('')
const url=new URL(`/pay/${props.qr.id}`,window.location.origin).href
watch(()=>props.qr.id,async()=>{try{image.value=await QRCode.toDataURL(url,{width:480,margin:2,color:{dark:'#174e3b',light:'#ffffff'},errorCorrectionLevel:'M'})}catch{error.value='Не удалось создать изображение QR'}},{immediate:true})
async function copy(){try{await navigator.clipboard.writeText(url);store.notify('Платёжная ссылка скопирована')}catch{error.value='Не удалось скопировать. Выделите ссылку вручную.'}}
function download(){const a=document.createElement('a');a.href=image.value;a.download=`tipro-${props.qr.id}.png`;a.click()}
</script>
<template><article class="panel qr-card"><div class="qr-card-top"><span class="tag">{{ qr.type==='receipt'?'На один чек':'Персональный' }}</span><span class="status" :class="!qr.active?'cancelled':qr.used?'cancelled':'success'"><i></i>{{ !qr.active?'Выключен':qr.used?'Использован':'Активен' }}</span></div><div class="qr-image"><img v-if="image" :src="image" :alt="`QR для ${employeeName}`"><span v-else class="muted">{{ error || 'Создаём QR…' }}</span><span class="qr-center">t.</span></div><h2>{{ employeeName }}</h2><p class="muted">{{ qr.label }}</p><div class="qr-url"><Link2 :size="15"/><input :value="url" readonly aria-label="Платёжная ссылка"><button class="icon-btn" @click="copy" aria-label="Скопировать ссылку"><Copy :size="15"/></button></div><p v-if="error" class="error-text">{{ error }}</p><div class="qr-actions"><RouterLink :to="`/pay/${qr.id}`" class="btn btn-outline btn-small" target="_blank">Открыть<ArrowUpRight :size="15"/></RouterLink><button class="icon-btn" @click="download" :disabled="!image" aria-label="Скачать QR в PNG" title="Скачать PNG"><Download :size="18"/></button><button class="icon-btn" @click="emit('toggle',qr)" :aria-label="qr.active?'Выключить QR':'Включить QR'" :title="qr.active?'Выключить QR':'Включить QR'"><Power :size="17"/></button></div></article></template>
