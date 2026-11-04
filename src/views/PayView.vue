<script setup>
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { ArrowRight, ArrowLeft, ShieldCheck, Check, X, RotateCcw, AlertCircle, Coffee, UsersRound } from 'lucide-vue-next'
import BrandLogo from '../components/BrandLogo.vue'
import GoalProgress from '../components/GoalProgress.vue'
import { api } from '../api'
import { applyRestaurantLanguage } from '../i18n'
import { money, initials } from '../utils/format'
import { useAppStore } from '../stores/app'
import { currencies, currencyStep, currencySymbol } from '../utils/currency'

const route = useRoute(), store = useAppStore()
const data = ref(null), loading = ref(true), state = ref('choose'), error = ref('')
const checking = ref(false)
const currency = computed(() => data.value?.qr.currency || 'RUB')
const selectedId = ref(''), amount = ref(300), scenario = ref('success'), paid = ref(null), cancelling = ref(false)
const employee = computed(() => data.value?.employees.find(e => e.id === selectedId.value))
const amountValid = computed(() => { const value=Number(amount.value),factor=10**(currencies[currency.value]||0); return Number.isFinite(value)&&value>0&&value<=10000000&&Math.abs(value*factor-Math.round(value*factor))<0.000001 })
const presets = computed(() => [150,300,500].map(value=>({label:money(value,currency.value),amount:value})))
const payMoney = value => money(value,currency.value)
function setPreset(preset){amount.value=preset.amount}

let controller, loadVersion = 0

async function load() {
  const version = ++loadVersion
  loading.value = true; error.value = ''; state.value = 'choose'; data.value = null; selectedId.value = ''
  try {
    const result = route.params.merchantId
      ? await api.resolveRestaurant(route.params.merchantId, typeof route.query.qr === 'string' ? route.query.qr : '')
      : await api.resolveQr(route.params.id)
    if (version !== loadVersion) return
    data.value = result
    applyRestaurantLanguage(result.merchant.language)
    const resumed=await api.resumePayment(result.qr.id,result.employees.map(e=>e.id))
    if(version!==loadVersion)return
    if(resumed){paid.value=resumed;selectedId.value=resumed.employeeId;amount.value=resumed.amount;state.value=resumed.status}

  } catch (e) { if (version === loadVersion) { error.value = e.message; state.value = e.code==='INVALID_QR'?'invalid':'error' } }
  finally { if (version === loadVersion) loading.value = false }
}
watch(() => [route.params.merchantId, route.params.id, route.query.qr], () => { controller?.abort(); scenario.value = 'success'; load() }, { immediate: true })
function select(person) { selectedId.value = person.id; setPreset(presets.value[Math.min(1,presets.value.length-1)]); error.value = ''; state.value = 'form' }
function scenarioChange() {
  error.value = ''
  if (scenario.value === 'invalid') { state.value = 'invalid'; error.value = 'Этот QR-код не найден или больше не действует.' }
  else if (data.value) state.value = employee.value ? 'form' : 'choose'
  else load()
}
async function pay() {
  if (!amountValid.value || !employee.value || state.value === 'processing') return
  state.value = 'processing'; cancelling.value = false; error.value = ''; controller = new AbortController()
  try {
    const result = await api.pay({ qrId: data.value.qr.id, employeeId: employee.value.id, amount: Number(amount.value), currency:currency.value, scenario: scenario.value, signal: controller.signal })
    paid.value = result; state.value = result.status
    if (result.status === 'success' && result.goalId === employee.value?.goal?.id && employee.value.goal.currency === result.currency) {
      employee.value.goal.raised += Number(result.amount)
    }
    if (store.session) store.load().catch(() => {})
  } catch (e) { error.value = e.message; state.value = e.code === 'INVALID_QR' ? 'invalid' : 'error' }
}
async function checkPending(cancelPayment=false){if(!paid.value?.publicToken||checking.value)return;checking.value=true;error.value='';try{const result=cancelPayment?await api.cancelPayment(paid.value.publicToken):await api.checkPayment(paid.value.publicToken);paid.value=result;state.value=result.status;if(store.session)await store.load()}catch(e){error.value=e.message}finally{checking.value=false}}
function cancel() { cancelling.value = true; controller?.abort() }
async function retry() { scenario.value = 'success'; await load() }
onBeforeRouteLeave(() => state.value === 'processing' ? false : true)
onBeforeUnmount(() => { controller?.abort(); loadVersion++ })
</script>
<template>
  <main class="pay-page">
    <header v-if="state!=='success'" class="pay-header"><BrandLogo/><LanguageSwitcher/><span><ShieldCheck :size="15"/>{{ $t('Без регистрации для гостей') }}</span></header>
    <div class="pay-layout">

      <div class="pay-right">
        <section class="pay-card" aria-live="polite">
          <div v-if="loading" class="empty"><span class="spinner"></span><h3>{{ $t('Открываем ресторан…') }}</h3></div>
          <template v-else-if="['choose','form'].includes(state) && data">
            <div class="pay-restaurant"><span class="restaurant-symbol"><Coffee :size="19"/></span>{{ data.merchant.name }}<span class="tag">{{ $t('ресторан') }}</span></div>
            <template v-if="state === 'choose'">
              <div class="restaurant-welcome"><h2>{{ $t('Выберите сотрудника') }}</h2><p>{{ $t('Чаевые получит выбранный сотрудник. Регистрация не нужна.') }}</p></div>
              <div v-if="!data.employees.length" class="empty compact"><UsersRound :size="32"/><h3>{{ $t('Команда скоро появится') }}</h3><p>{{ $t('Ресторан ещё не добавил активных сотрудников. Попросите администратора ресторана добавить сотрудников.') }}</p><button class="btn btn-outline" @click="load">{{ $t('Обновить') }}</button></div>
              <div class="restaurant-team">
                <button v-for="person in data.employees" :key="person.id" class="restaurant-person" @click="select(person)">
                  <div class="restaurant-person-head"><span class="avatar" :class="person.color">{{ initials(person.name) }}</span><div><strong>{{ person.name }}</strong><small>{{ person.role }}</small></div><ArrowRight :size="18"/></div>
                  <GoalProgress v-if="person.goal" :goal="person.goal"/><p v-else class="person-no-goal">{{ $t('Сказать спасибо за хороший сервис') }}</p>
                </button>
              </div>
              <p class="pay-safe"><ShieldCheck :size="14"/>{{ $t('Аккаунт гостя не нужен · демооплата') }}</p>
            </template>
            <template v-else-if="employee">
              <button class="text-link pay-back" @click="state='choose';selectedId=''" ><ArrowLeft :size="15"/>{{ $t('Выбрать другого сотрудника') }}</button>
              <div class="pay-person"><span class="avatar pay-avatar" :class="employee.color">{{ initials(employee.name) }}</span><h2>{{ employee.name }}</h2><p>{{ $t(employee.role) }}</p></div>
              <GoalProgress :goal="employee.goal"/><p v-if="employee.goal && employee.goal.currency!==currency" class="muted small-text">{{ $t('Цель в {goalCurrency}. Эти чаевые в {currency} сохранятся в статистике, но не изменят прогресс цели.',{goalCurrency:employee.goal.currency,currency}) }}</p>
              <h3 class="pay-choose">{{ $t('Сумма чаевых') }}</h3>
              <div class="tip-options"><button v-for="preset in presets" :key="preset.label" @click="setPreset(preset)" :class="{selected:Number(amount)===preset.amount}">{{ preset.label }}</button></div>
              <label class="custom-amount">{{ $t('Или своя сумма') }}<div><input v-model="amount" type="number" :min="currencyStep(currency)" max="10000000" :step="currencyStep(currency)" inputmode="numeric" :aria-label="$t('Своя сумма чаевых')"><span>{{ currencySymbol(currency) }} {{ currency }}</span></div></label>
              <p v-if="!amountValid" class="error-text">{{ $t('Введите сумму от') }} {{ currencyStep(currency) }} {{ $t('до 10 000 000') }} {{ currency }}.</p>
              <div class="pay-total"><span>{{ $t('Ваши чаевые') }}</span><strong>{{ payMoney(Number(amount)||0) }}</strong></div>
              <button class="btn btn-primary pay-submit" :disabled="!amountValid" @click="pay">{{ $t('Оплатить чаевые') }}<ArrowRight :size="19"/></button>
              <p class="pay-safe"><ShieldCheck :size="14"/>{{ $t('Демо: деньги не списываются') }}</p><button class="text-link pay-cancel" @click="state='cancelled'">{{ $t('Отменить') }}</button>
            </template>
          </template>
          <div v-else-if="state==='processing'" class="pay-result"><div class="result-icon processing"><span class="spinner"></span></div><h2>{{ $t('Обработка платежа') }}</h2><p>{{ $t('Обрабатываем демоплатёж') }} {{ payMoney(amount) }}.<br>{{ $t('Это займёт пару секунд.') }}</p><button class="btn btn-outline full" @click="cancel" :disabled="cancelling">{{ cancelling?$t('Отменяем…'):$t('Отменить оплату') }}</button></div>
          <div v-else-if="state==='pending'" class="pay-result"><div class="result-icon processing"><ShieldCheck :size="30"/></div><h2>{{ $t('Ожидаем подтверждение') }}</h2><p>{{ $t('Платёж') }} {{ payMoney(paid?.amount) }} {{ $t('создан на сервере. Подтверждение ещё не получено.') }}</p><p v-if="error" class="error-text" role="alert">{{ $t(error) }}</p><button class="btn btn-primary full" :disabled="checking" @click="checkPending()">{{ checking?$t('Проверяем…'):$t('Проверить статус') }}</button><button class="btn btn-outline full" :disabled="checking" @click="checkPending(true)">{{ $t('Отменить платёж') }}</button></div>
          <div v-else-if="state==='success'" class="pay-result"><div class="result-icon success"><Check :size="38"/></div><h2>{{ $t('Спасибо за чаевые!') }}</h2><p>{{ $t('Вы отправили {amount} сотруднику {name}.', {amount:payMoney(paid?.amount),name:employee?.name}) }}</p><p>{{ $t('Спасибо, что цените нашу работу. Хорошего вам дня!') }}</p><p class="muted small-text">{{ $t('Оплата завершена. Эту страницу можно закрыть.') }}</p></div>
          <div v-else class="pay-result"><div class="result-icon" :class="state==='cancelled'?'neutral':'warning'"><X v-if="state==='cancelled'" :size="34"/><AlertCircle v-else :size="34"/></div><h2>{{ state==='cancelled'?$t('Оплата отменена'):state==='declined'?$t('Не получилось оплатить'):state==='invalid'?$t('QR-код недействителен'):$t('Что-то пошло не так') }}</h2><p>{{ state==='cancelled'?$t('Вы отменили оплату. Деньги не списывались.'):state==='declined'?$t('Демобанк отклонил платёж. Вы можете попробовать снова.'):$t(error) }}</p><p v-if="state==='invalid'" class="muted small-text">{{ $t('Попросите ресторан показать действующий QR-код.') }}</p><button v-if="data" class="btn btn-primary full" @click="retry"><RotateCcw :size="17"/>{{ $t('Вернуться к ресторану') }}</button><RouterLink v-else to="/" class="btn btn-outline full">{{ $t('На главную') }}</RouterLink></div>
        </section>
        <details v-if="data?.demoControls && state!=='success'" class="demo-controls"><summary>{{ $t('Настройки демооплаты') }}</summary><label>{{ $t('Сценарий оплаты') }}<select v-model="scenario" @change="scenarioChange" :disabled="loading || ['processing','pending'].includes(state)"><option value="success">{{ $t('Успешная оплата') }}</option><option value="pending">{{ $t('Ожидание подтверждения') }}</option><option value="declined">{{ $t('Отказ банка') }}</option><option value="invalid">{{ $t('Недействительный QR') }}</option><option value="cancelled">{{ $t('Отмена платежа') }}</option></select></label><p>{{ $t('QR ресторана постоянный и подходит для следующих гостей. Отказ и отмена сохраняются в истории, но не увеличивают чаевые и прогресс цели.') }}</p></details>
      </div>
    </div><footer v-if="state!=='success'" class="pay-footer">{{ $t('Работает на') }} <strong>tipro.</strong><span>{{ $t('Демонстрационная оплата') }}</span></footer>
  </main>
</template>
