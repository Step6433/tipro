<script setup>
import { ref } from 'vue'
import { Plus, QrCode, Info } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import BaseModal from '../components/BaseModal.vue'
import QrCard from '../components/QrCard.vue'
const store=useAppStore(),open=ref(false),busy=ref(false),error=ref(''),pageError=ref('')
const label=ref('')
function create(){label.value='QR ресторана';error.value='';open.value=true}
async function save(){busy.value=true;error.value='';try{await api.createQr({label:label.value,currency:store.merchant?.currency});await store.load();open.value=false;store.notify('QR-код готов к скачиванию')}catch(e){error.value=e.message}finally{busy.value=false}}
async function toggle(q){pageError.value='';try{await api.toggleQr(q.id);await store.load();store.notify('Статус QR-кода обновлён')}catch(e){pageError.value=e.message}}
</script>
<template>
  <div class="page-heading"><div><h1>{{ $t('QR-код ресторана') }}</h1><p>{{ $t('Гость сканирует код, выбирает сотрудника и оставляет чаевые.') }}</p></div><button class="btn btn-primary" @click="create"><Plus :size="18"/>{{ $t('Создать QR-код') }}</button></div>
  <div class="info-banner"><Info :size="20"/><span>{{ $t('Создайте QR один раз и скачайте PNG. Код не истекает и не меняется после оплаты. При необходимости его можно отключить вручную.') }}</span></div>
  <p v-if="pageError" class="error-banner" role="alert">{{ $t(pageError) }}</p>
  <div v-if="!store.qrs.length" class="panel empty"><QrCode :size="36"/><h3>{{ $t('Создайте QR ресторана') }}</h3><p>{{ $t('Один код для всех гостей. Разместите его там, где удобно посетителям.') }}</p><button class="btn btn-outline" @click="create">{{ $t('Создать QR-код') }}</button></div>
  <div class="qr-grid"><QrCard v-for="q in store.qrs" :key="q.id" :qr="q" :restaurant-name="store.merchant?.name" @toggle="toggle"/></div>
  <BaseModal v-if="open" :title="$t('QR-код ресторана')" :subtitle="$t('Постоянная ссылка для чаевых.')" @close="!busy&&(open=false)">
    <form class="form-stack" @submit.prevent="save"><label>{{ $t('Название') }}<input v-model="label" required maxlength="80" :placeholder="$t('Например, QR ресторана')"></label><p class="muted small-text">{{ $t('Код откроет страницу «') }}{{ store.merchant?.name }}{{ $t('». Гость выберет сотрудника и сумму чаевых.') }}</p><p v-if="error" class="error-text" role="alert">{{ $t(error) }}</p><button class="btn btn-primary" :disabled="busy">{{ busy?$t('Создаём…'):$t('Создать QR-код') }}</button></form>
  </BaseModal>
</template>
