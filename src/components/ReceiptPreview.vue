<script setup>
import { ref, onUnmounted } from 'vue'
import { Printer, Download } from 'lucide-vue-next'
import { money, dateTime } from '../utils/format'
import { receiptPng } from '../utils/receipt'
const props=defineProps({qr:Object,restaurantName:String,url:String,image:String})
const busy=ref(false),error=ref('')
const createdAt=props.qr.createdAt||new Date().toISOString()
function finishPrint(){document.body.classList.remove('printing-receipt')}
function print(){error.value='';document.body.classList.add('printing-receipt');window.addEventListener('afterprint',finishPrint,{once:true});try{window.print()}catch{finishPrint();error.value='Не удалось открыть печать. Скачайте чек в PNG.'}}
onUnmounted(()=>{finishPrint();window.removeEventListener('afterprint',finishPrint)})
async function download(){busy.value=true;error.value='';try{const url=await receiptPng({qr:props.qr,restaurantName:props.restaurantName,url:props.url});const a=document.createElement('a');a.href=url;a.download=`tipro-receipt-${props.qr.id}.png`;a.click()}catch(e){error.value=e.message||'Не удалось скачать чек.'}finally{busy.value=false}}
</script>
<template><div class="receipt-preview"><div class="receipt-print-sheet"><h3>{{ restaurantName }}</h3><p class="receipt-caption">Демонстрационный предчек</p><p class="receipt-number">{{ qr.receipt?`Чек № ${qr.receipt.number}`:'Макет чека' }}</p><p class="receipt-date">{{ dateTime(createdAt) }}</p><div class="receipt-total"><span>Сумма заказа</span><strong>{{ qr.receipt?money(qr.receipt.billAmount,qr.currency):'Не указана' }}</strong></div><h4>Оставить чаевые</h4><p>Сканируйте QR-код<br>и выберите сотрудника</p><img v-if="image" :src="image" :alt="`QR для чаевых в ${restaurantName}`"><p>Чаевые не входят в сумму заказа.<br>Регистрация гостя не нужна.</p><p class="receipt-caption receipt-disclaimer">Не является кассовым чеком.</p></div><p v-if="error" class="error-text" role="alert">{{ error }}</p><div class="receipt-tools"><button class="btn btn-primary" :disabled="!image" @click="print"><Printer :size="17"/>Печать</button><button class="btn btn-outline" :disabled="busy||!image" @click="download"><Download :size="17"/>{{ busy?'Готовим…':'Скачать чек PNG' }}</button></div></div></template>
