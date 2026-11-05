<script setup>
import { computed, ref, watch } from 'vue'
import QRCode from 'qrcode'
import { Copy, Download, ArrowUpRight, Link2, Power } from 'lucide-vue-next'
import { dateTime } from '../utils/format'
import { useAppStore } from '../stores/app'
const props=defineProps({qr:Object,restaurantName:String,employeeName:String})
const emit=defineEmits(['toggle'])
const store=useAppStore(), image=ref(''), error=ref('')
const expired=computed(()=>props.qr.expiresAt && new Date(props.qr.expiresAt)<=new Date())
const usable=computed(()=>props.qr.active && !expired.value)
const status=computed(()=>props.qr.state==='used'?'Использован':props.qr.state==='legacy'?'Нужен новый код':expired.value?'Срок истёк':props.qr.active?'Активен':'Выключен')
const url=computed(()=>props.qr.url || new URL(`/restaurant/${props.qr.merchantId}?qr=${encodeURIComponent(props.qr.id)}`,window.location.origin).href)
watch(url,async(value)=>{try{error.value='';image.value=await QRCode.toDataURL(value,{width:480,margin:4,color:{dark:'#000000',light:'#ffffff'},errorCorrectionLevel:'M'})}catch{error.value='Не удалось создать изображение QR'}},{immediate:true})
async function copy(){try{await navigator.clipboard.writeText(url.value);store.notify('Платёжная ссылка скопирована')}catch{error.value='Не удалось скопировать. Выделите ссылку вручную.'}}
function download(){const a=document.createElement('a');a.href=image.value;a.download=`tipro-employee-${props.qr.employeeId}-${props.qr.nonce.slice(0,10)}.png`;a.click()}
</script>
<template><article class="panel qr-card"><div class="qr-card-top"><span class="tag">{{ $t('QR сотрудника') }}</span><span class="status" :class="!usable?'cancelled':'success'"><i></i>{{ $t(status) }}</span></div><div class="qr-image"><img v-if="image" :src="image" :alt="$t('QR для {0}', {0: restaurantName})"><span v-else class="muted">{{ error || $t('Создаём QR…') }}</span><span class="qr-center">t.</span></div><h2>{{ restaurantName }}</h2><p><strong>{{ employeeName }}</strong></p><p class="muted">{{ qr.label }}</p><p v-if="qr.expiresAt" class="muted small-text">{{ $t('Действует до') }} {{ dateTime(qr.expiresAt) }}</p><p v-if="qr.usedAt" class="muted small-text">{{ $t('Использован') }} {{ dateTime(qr.usedAt) }}</p><div class="qr-url"><Link2 :size="15"/><input :value="url" readonly :aria-label="$t('Платёжная ссылка')"><button class="icon-btn" @click="copy" :aria-label="$t('Скопировать ссылку')"><Copy :size="15"/></button></div><p v-if="error" class="error-text">{{ $t(error) }}</p><div class="qr-actions"><RouterLink v-if="usable" :to="`/restaurant/${qr.merchantId}?qr=${qr.id}`" class="btn btn-outline btn-small" target="_blank">{{ $t('Открыть') }}<ArrowUpRight :size="15"/></RouterLink><button class="icon-btn" @click="download" :disabled="!image || !usable" :aria-label="$t('Скачать QR в PNG')" :title="$t('Скачать PNG')"><Download :size="18"/></button><button v-if="!['used','legacy','expired'].includes(qr.state) && !expired" class="icon-btn" @click="emit('toggle',qr)" :aria-label="qr.active?$t('Выключить QR'):$t('Включить QR')" :title="qr.active?$t('Выключить QR'):$t('Включить QR')"><Power :size="17"/></button></div><button class="btn btn-primary full" @click="download" :disabled="!image || !usable"><Download :size="18"/>{{ $t('Скачать QR-код') }}</button></article></template>
