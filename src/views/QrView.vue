<script setup>
import { ref } from 'vue'
import { Plus, ReceiptText, Info } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import BaseModal from '../components/BaseModal.vue'
import QrCard from '../components/QrCard.vue'
const store=useAppStore(),open=ref(false),busy=ref(false),error=ref(''),pageError=ref('')
const form=ref({receiptNumber:'',billAmount:''})
function create(){form.value={receiptNumber:'',billAmount:''};error.value='';open.value=true}
async function save(){busy.value=true;error.value='';try{await api.createQr(form.value);await store.load();open.value=false;store.notify('Чек с QR-кодом готов')}catch(e){error.value=e.message}finally{busy.value=false}}
async function toggle(q){pageError.value='';try{await api.toggleQr(q.id);await store.load();store.notify('Статус QR-кода обновлён')}catch(e){pageError.value=e.message}}
</script>
<template>
  <div class="page-heading"><div><h1>QR на чеке</h1><p>Гость сканирует код с чека, открывает ресторан и выбирает сотрудника.</p></div><button class="btn btn-primary" @click="create"><Plus :size="18"/>Создать чек с QR</button></div>
  <div class="info-banner"><Info :size="20"/><span>Создайте демонстрационный предчек и скачайте его в PNG или распечатайте. В действующей кассе платёжная ссылка должна добавляться в шаблон чека через кассовую систему. Чаевые оплачиваются отдельно от заказа.</span></div>
  <p v-if="pageError" class="error-banner" role="alert">{{ pageError }}</p>
  <div v-if="!store.qrs.length" class="panel empty"><ReceiptText :size="36"/><h3>Первый чек с QR-кодом</h3><p>Укажите номер и сумму заказа. Код будет расположен внизу чека и откроет страницу вашего ресторана.</p><button class="btn btn-outline" @click="create">Создать чек с QR</button></div>
  <div class="qr-grid"><QrCard v-for="q in store.qrs" :key="q.id" :qr="q" :restaurant-name="store.merchant?.name" @toggle="toggle"/></div>
  <BaseModal v-if="open" title="Чек с QR-кодом" subtitle="Макет для демонстрации, без подключения к кассе." @close="!busy&&(open=false)">
    <form class="form-stack" @submit.prevent="save"><label>Номер чека<input v-model="form.receiptNumber" required maxlength="40" placeholder="Например, 1042"></label><label>Сумма заказа, ₽<input v-model="form.billAmount" type="number" required min="1" max="10000000" step="1" inputmode="numeric" placeholder="2800"></label><p class="muted small-text">QR ведёт на страницу «{{ store.merchant?.name }}». Гость выбирает сотрудника и сумму чаевых. Этот макет не является кассовым чеком.</p><p v-if="error" class="error-text" role="alert">{{ error }}</p><button class="btn btn-primary" :disabled="busy">{{ busy?'Создаём…':'Создать чек' }}</button></form>
  </BaseModal>
</template>
