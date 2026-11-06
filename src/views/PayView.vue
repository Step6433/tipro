<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { ArrowRight, ShieldCheck, Check, AlertCircle, Coffee } from 'lucide-vue-next'
import BrandLogo from '../components/BrandLogo.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import GoalProgress from '../components/GoalProgress.vue'
import { api } from '../api'
import { applyRestaurantLanguage } from '../i18n'
import { money, initials } from '../utils/format'
import { currencyStep, currencySymbol } from '../utils/currency'

const route=useRoute(),data=ref(null),loading=ref(true),state=ref('welcome'),error=ref(''),busy=ref(false)
const amount=ref(0),percent=ref(10),scenario=ref('success'),paid=ref(null)
const employee=computed(()=>data.value?.employees[0])
const currency=computed(()=>data.value?.qr.currency||'RUB')
const bill=computed(()=>Number(data.value?.qr.receipt?.billAmount||0))
const maxTip=computed(()=>Math.floor((bill.value*.5+Number.EPSILON)/currencyStep(currency.value))*currencyStep(currency.value))
const amountValid=computed(()=>Number.isFinite(Number(amount.value))&&Number(amount.value)>=0&&Number(amount.value)<=maxTip.value&&Math.abs(Number(amount.value)/currencyStep(currency.value)-Math.round(Number(amount.value)/currencyStep(currency.value)))<.00001)
const presets=computed(()=>[...new Set([0,5,10,15,20,...(data.value?.merchant.tipPercentages||[])])].sort((a,b)=>a-b))
const total=computed(()=>bill.value+Number(amount.value||0))
const fmt=value=>money(value,currency.value)
let version=0
function choosePercent(value){percent.value=value;amount.value=Math.min(maxTip.value,Math.round(bill.value*value/100/currencyStep(currency.value))*currencyStep(currency.value))}
async function load(){
 const current=++version;loading.value=true;error.value='';paid.value=null;state.value='welcome'
 try{
  const result=route.params.merchantId?await api.resolveRestaurant(route.params.merchantId,route.query.qr||''):await api.resolveQr(route.params.id)
  if(current!==version)return
  data.value=result;applyRestaurantLanguage(result.merchant.language);choosePercent(10)
  const resumed=await api.resumePayment(result.qr.id,result.employees.map(e=>e.id))
  if(current!==version)return
  if(resumed){paid.value=resumed;amount.value=resumed.amount;state.value=resumed.status==='created'?'confirm':resumed.status}
 }catch(e){if(current===version){error.value=e.message;state.value='invalid'}}finally{if(current===version)loading.value=false}
}
watch(()=>[route.params.merchantId,route.params.id,route.query.qr],load,{immediate:true})
async function prepare(){
 if(busy.value||!amountValid.value)return
 busy.value=true;error.value=''
 try{paid.value=await api.preparePayment({qrId:data.value.qr.id,employeeId:employee.value.id,receiptId:data.value.qr.receipt.id,amount:Number(amount.value),currency:currency.value,scenario:scenario.value});state.value=paid.value.status==='created'?'confirm':paid.value.status}
 catch(e){error.value=e.message}finally{busy.value=false}
}
async function confirm(){
 if(busy.value)return
 busy.value=true;state.value='processing';error.value=''
 try{paid.value=await api.confirmPayment(paid.value.publicToken,{wait:scenario.value!=='pending'});state.value=paid.value.status}
 catch(e){error.value=e.message;state.value='uncertain'}finally{busy.value=false}
}
async function cancel(){
 if(busy.value)return
 busy.value=true;error.value=''
 try{if(paid.value?.status==='created'){paid.value=await api.cancelPayment(paid.value.publicToken);state.value=paid.value.status}else state.value='cancelled'}
 catch(e){error.value=e.message}finally{busy.value=false}
}
async function checkStatus(){
 if(busy.value||!paid.value?.publicToken)return
 busy.value=true;error.value=''
 try{paid.value=await api.checkPayment(paid.value.publicToken);state.value=paid.value.status==='created'?'confirm':paid.value.status}catch(e){error.value=e.message}finally{busy.value=false}
}
onBeforeRouteLeave(()=>!busy.value)
</script>
<template>
 <main class="pay-page">
  <header v-if="state!=='success'" class="pay-header"><BrandLogo/><LanguageSwitcher/><span><ShieldCheck :size="15"/>{{ $t('Без регистрации для гостей') }}</span></header>
  <div class="pay-layout"><div class="pay-right"><section class="pay-card" aria-live="polite">
   <div v-if="loading" class="empty"><span class="spinner"></span>{{ $t('Открываем ресторан…') }}</div>
   <template v-else-if="data&&['welcome','form','confirm'].includes(state)">
    <div class="pay-restaurant"><Coffee :size="19"/>{{ data.merchant.name }}</div>
    <div class="pay-person"><span class="avatar pay-avatar" :class="employee?.color">{{ initials(employee?.name||'') }}</span><h2>{{ employee?.name }}</h2><p>{{ $t(employee?.role) }}</p></div>
    <p class="muted">{{ $t('Чек') }} № {{ data.qr.receipt.number }}</p>
    <div class="pay-total"><span>{{ $t('Сумма чека') }}</span><strong>{{ fmt(bill) }}</strong></div>
    <template v-if="state==='welcome'"><GoalProgress :goal="employee?.goal"/><p class="pay-intro">{{ $t('На следующем шаге выберите сумму чаевых.') }}</p><button class="btn btn-primary full" @click="state='form'">{{ $t('Продолжить') }}<ArrowRight :size="18"/></button></template>
    <template v-else-if="state==='form'">
     <h3 class="pay-choose">{{ $t('Чаевые') }}</h3><div class="tip-options"><button v-for="p in presets" :key="p" :class="{selected:percent===p}" @click="choosePercent(p)">{{ p }}%</button></div>
     <label class="custom-amount">{{ $t('Или своя сумма') }}<div><input v-model="amount" @input="percent=null" type="number" min="0" :max="maxTip" :step="currencyStep(currency)" inputmode="decimal"><span>{{ currencySymbol(currency) }}</span></div></label>
     <p v-if="!amountValid" class="error-text">{{ $t('Чаевые должны составлять от 0 до 50% суммы чека.') }}</p>
     <div class="pay-total"><span>{{ $t('Итого к оплате') }}</span><strong>{{ fmt(total) }}</strong></div>
     <button class="btn btn-primary full" :disabled="busy||!amountValid" @click="prepare">{{ $t('Перейти к подтверждению') }}</button><button class="text-link pay-cancel" :disabled="busy" @click="cancel">{{ $t('Отменить') }}</button>
    </template>
    <template v-else><h3>{{ $t('Подтверждение оплаты') }}</h3><div class="pay-total"><span>{{ $t('Чаевые') }}</span><strong>{{ fmt(paid.amount) }}</strong></div><div class="pay-total"><span>{{ $t('Итого к оплате') }}</span><strong>{{ fmt(paid.amountTotal) }}</strong></div><button class="btn btn-primary full" :disabled="busy" @click="confirm">{{ $t('Подтвердить оплату') }}</button><button class="btn btn-outline full" :disabled="busy" @click="cancel">{{ $t('Отменить платёж') }}</button></template>
    <p class="pay-safe"><ShieldCheck :size="14"/>{{ $t('Демо: деньги не списываются') }}</p>
   </template>
   <div v-else-if="state==='processing'" class="pay-result"><span class="spinner"></span><h2>{{ $t('Обработка платежа') }}</h2><p>{{ $t('Это займёт пару секунд.') }}</p></div>
   <div v-else-if="['pending','uncertain'].includes(state)" class="pay-result"><h2>{{ $t('Ожидаем подтверждение') }}</h2><p>{{ $t('Обрабатываем, проверьте через минуту') }}</p><button class="btn btn-primary full" :disabled="busy" @click="checkStatus">{{ $t('Проверить статус') }}</button></div>
   <div v-else-if="state==='success'" class="pay-result"><div class="result-icon success"><Check :size="38"/></div><h2>{{ $t('Спасибо за чаевые!') }}</h2><p>{{ $t('Вы отправили {amount} сотруднику {name}.',{amount:fmt(paid?.amount),name:employee?.name}) }}</p><p>{{ $t('Оплата завершена. Эту страницу можно закрыть.') }}</p></div>
   <div v-else class="pay-result"><div class="result-icon warning"><AlertCircle :size="34"/></div><h2>{{ state==='cancelled'?$t('Оплата отменена'):state==='declined'?$t('Не получилось оплатить'):$t('QR-код недействителен') }}</h2><p>{{ state==='cancelled'?$t('Вы отменили оплату. Деньги не списывались.'):state==='declined'?$t(paid?.errorCode==='QR_EXPIRED'?'Срок действия QR-кода истёк. Попросите новый код у ресторана.':paid?.errorCode==='MERCHANT_BLOCKED'?'Ресторан заблокирован.':'Демобанк отклонил платёж. Вы можете попробовать снова.'):$t(error) }}</p><button v-if="data&&['cancelled','declined'].includes(state)" class="btn btn-outline full" @click="load">{{ $t('Попробовать снова') }}</button></div>
   <p v-if="error&&state!=='invalid'" class="error-text" role="alert">{{ $t(error) }}</p>
  </section>
  <details v-if="data?.demoControls&&['welcome','form'].includes(state)" class="demo-controls"><summary>{{ $t('Настройки демооплаты') }}</summary><label>{{ $t('Сценарий оплаты') }}<select v-model="scenario" :disabled="busy"><option value="success">{{ $t('Успешная оплата') }}</option><option value="declined">{{ $t('Отказ банка') }}</option><option value="pending">{{ $t('Ожидание подтверждения') }}</option></select></label></details>
  </div></div><footer v-if="state!=='success'" class="pay-footer">{{ $t('Демонстрационная оплата') }}</footer>
 </main>
</template>
