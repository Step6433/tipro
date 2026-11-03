<script setup>
import { ref, watch } from 'vue'
import QRCode from 'qrcode'
import { Copy, Download, ArrowUpRight, Link2, Power, ReceiptText } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import BaseModal from './BaseModal.vue'
import ReceiptPreview from './ReceiptPreview.vue'
const props=defineProps({qr:Object,restaurantName:String})
const emit=defineEmits(['toggle'])
const store=useAppStore(), image=ref(''), error=ref(''), preview=ref(false)
const url=new URL(`/restaurant/${props.qr.merchantId}?qr=${props.qr.id}`,window.location.origin).href
watch(()=>props.qr.id,async()=>{try{image.value=await QRCode.toDataURL(url,{width:480,margin:4,color:{dark:'#000000',light:'#ffffff'},errorCorrectionLevel:'M'})}catch{error.value='Не удалось создать изображение QR'}},{immediate:true})
async function copy(){try{await navigator.clipboard.writeText(url);store.notify('Платёжная ссылка скопирована')}catch{error.value='Не удалось скопировать. Выделите ссылку вручную.'}}
function download(){const a=document.createElement('a');a.href=image.value;a.download=`tipro-${props.qr.id}.png`;a.click()}
</script>
<template><article class="panel qr-card"><div class="qr-card-top"><span class="tag">QR для чека</span><span class="status" :class="!qr.active?'cancelled':'success'"><i></i>{{ !qr.active?'Выключен':'Активен' }}</span></div><div class="qr-image"><img v-if="image" :src="image" :alt="`QR для ${restaurantName}`"><span v-else class="muted">{{ error || 'Создаём QR…' }}</span><span class="qr-center">t.</span></div><h2>{{ restaurantName }}</h2><p class="muted">{{ qr.label }}</p><div class="qr-url"><Link2 :size="15"/><input :value="url" readonly aria-label="Платёжная ссылка"><button class="icon-btn" @click="copy" aria-label="Скопировать ссылку"><Copy :size="15"/></button></div><p v-if="error" class="error-text">{{ error }}</p><div class="qr-actions"><RouterLink :to="`/restaurant/${qr.merchantId}?qr=${qr.id}`" class="btn btn-outline btn-small" target="_blank">Открыть<ArrowUpRight :size="15"/></RouterLink><button class="icon-btn" @click="download" :disabled="!image" aria-label="Скачать QR в PNG" title="Скачать PNG"><Download :size="18"/></button><button class="icon-btn" @click="emit('toggle',qr)" :aria-label="qr.active?'Выключить QR':'Включить QR'" :title="qr.active?'Выключить QR':'Включить QR'"><Power :size="17"/></button></div><button class="btn btn-outline full receipt-preview-btn" @click="preview=true" :disabled="!image"><ReceiptText :size="17"/>Посмотреть чек</button></article><BaseModal v-if="preview" title="Чек с QR-кодом" @close="preview=false"><ReceiptPreview :qr="qr" :restaurant-name="restaurantName" :url="url" :image="image"/></BaseModal></template>
