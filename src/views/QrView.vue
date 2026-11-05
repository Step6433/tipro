<script setup>
import { computed, ref } from 'vue'
import { Plus, QrCode, Info } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import BaseModal from '../components/BaseModal.vue'
import QrCard from '../components/QrCard.vue'
const store=useAppStore(),open=ref(false),busy=ref(false),error=ref(''),pageError=ref('')
const label=ref(''),employeeId=ref('')
const employees=computed(()=>store.employees.filter(e=>e.active))
function create(){label.value='QR сотрудника';employeeId.value=employees.value[0]?.id||'';error.value='';open.value=true}
async function save(){busy.value=true;error.value='';try{await api.createQr({label:label.value,employeeId:employeeId.value,currency:store.merchant?.currency});await store.load();open.value=false;store.notify('QR-код готов к скачиванию')}catch(e){error.value=e.message}finally{busy.value=false}}
async function toggle(q){pageError.value='';try{await api.toggleQr(q.id);await store.load();store.notify('Статус QR-кода обновлён')}catch(e){pageError.value=e.message}}
</script>
<template>
  <div class="page-heading"><div><h1>{{ $t('QR-коды сотрудников') }}</h1><p>{{ $t('Гость сканирует QR и оставляет чаевые указанному сотруднику.') }}</p></div><button class="btn btn-primary" @click="create"><Plus :size="18"/>{{ $t('Создать QR-код') }}</button></div>
  <div class="info-banner"><Info :size="20"/><span>{{ $t('Каждый QR привязан к одному сотруднику, действует 24 часа и становится недействительным после успешной оплаты. Для следующего платежа создайте новый код.') }}</span></div>
  <p v-if="pageError" class="error-banner" role="alert">{{ $t(pageError) }}</p>
  <div v-if="!store.qrs.length" class="panel empty"><QrCode :size="36"/><h3>{{ $t('Создайте QR сотрудника') }}</h3><p>{{ $t('Выберите сотрудника, создайте одноразовый код и скачайте PNG.') }}</p><button class="btn btn-outline" @click="create">{{ $t('Создать QR-код') }}</button></div>
  <div class="qr-grid"><QrCard v-for="q in store.qrs" :key="q.id" :qr="q" :restaurant-name="store.merchant?.name" :employee-name="store.employeeName(q.employeeId)" @toggle="toggle"/></div>
  <BaseModal v-if="open" :title="$t('QR-коды сотрудников')" :subtitle="$t('Одна успешная оплата в течение 24 часов.')" @close="!busy&&(open=false)">
    <form class="form-stack" @submit.prevent="save"><label>{{ $t('Получатель чаевых') }}<select v-model="employeeId" required><option value="" disabled>{{ $t('Выберите сотрудника') }}</option><option v-for="e in employees" :key="e.id" :value="e.id">{{ e.name }}</option></select></label><p v-if="!employees.length" class="muted small-text">{{ $t('Сначала добавьте активного сотрудника в команду.') }}</p><label>{{ $t('Название') }}<input v-model="label" required maxlength="80" :placeholder="$t('Например, QR сотрудника')"></label><p class="muted small-text">{{ $t('Получателя нельзя изменить на странице оплаты. Срок действия — 24 часа с момента создания.') }}</p><p v-if="error" class="error-text" role="alert">{{ $t(error) }}</p><button class="btn btn-primary" :disabled="busy || !employeeId">{{ busy?$t('Создаём…'):$t('Создать QR-код') }}</button></form>
  </BaseModal>
</template>
