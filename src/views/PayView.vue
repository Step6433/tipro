<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { Heart, ArrowRight, ArrowLeft, ShieldCheck, Check, X, RotateCcw, AlertCircle, Coffee, UsersRound } from 'lucide-vue-next'
import BrandLogo from '../components/BrandLogo.vue'
import GoalProgress from '../components/GoalProgress.vue'
import { api } from '../api'
import { money, initials } from '../utils/format'
import { useAppStore } from '../stores/app'

const route = useRoute(), store = useAppStore()
const data = ref(null), loading = ref(true), state = ref('choose'), error = ref('')
const selectedId = ref(''), amount = ref(300), scenario = ref('success'), paid = ref(null), cancelling = ref(false)
const employee = computed(() => data.value?.employees.find(e => e.id === selectedId.value))
const amountValid = computed(() => Number.isInteger(Number(amount.value)) && Number(amount.value) >= 10 && Number(amount.value) <= 50000)
const presets = [150, 300, 500]
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
  } catch (e) { if (version === loadVersion) { error.value = e.message; state.value = 'invalid' } }
  finally { if (version === loadVersion) loading.value = false }
}
watch(() => [route.params.merchantId, route.params.id, route.query.qr], () => { controller?.abort(); scenario.value = 'success'; load() }, { immediate: true })
function select(person) { selectedId.value = person.id; amount.value = 300; error.value = ''; state.value = 'form' }
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
    const result = await api.pay({ qrId: data.value.qr.id, employeeId: employee.value.id, amount: Number(amount.value), scenario: scenario.value, signal: controller.signal })
    paid.value = result; state.value = result.status
    if (store.session) store.load().catch(() => {})
  } catch (e) { error.value = e.message; state.value = e.code === 'INVALID_QR' ? 'invalid' : 'error' }
}
function cancel() { cancelling.value = true; controller?.abort() }
async function retry() { scenario.value = 'success'; await load() }
onBeforeRouteLeave(() => state.value === 'processing' ? false : true)
onBeforeUnmount(() => { controller?.abort(); loadVersion++ })
</script>
<template>
  <main class="pay-page">
    <header class="pay-header"><BrandLogo/><span><ShieldCheck :size="15"/>Без регистрации для гостей</span></header>
    <div class="pay-layout">

      <div class="pay-right">
        <section class="pay-card" aria-live="polite">
          <div v-if="loading" class="empty"><span class="spinner"></span><h3>Открываем ресторан…</h3></div>
          <template v-else-if="['choose','form'].includes(state) && data">
            <div class="pay-restaurant"><span class="restaurant-symbol"><Coffee :size="19"/></span>{{ data.merchant.name }}<span class="tag">ресторан</span></div>
            <template v-if="state === 'choose'">
              <div class="restaurant-welcome"><h2>Выберите сотрудника</h2><p>Чаевые получит выбранный сотрудник. Регистрация не нужна.</p></div>
              <div v-if="!data.employees.length" class="empty compact"><UsersRound :size="32"/><h3>Команда скоро появится</h3><p>Ресторан ещё не добавил активных сотрудников. Попросите администратора ресторана добавить сотрудников.</p><button class="btn btn-outline" @click="load">Обновить</button></div>
              <div class="restaurant-team">
                <button v-for="person in data.employees" :key="person.id" class="restaurant-person" @click="select(person)">
                  <div class="restaurant-person-head"><span class="avatar" :class="person.color">{{ initials(person.name) }}</span><div><strong>{{ person.name }}</strong><small>{{ person.role }}</small></div><ArrowRight :size="18"/></div>
                  <GoalProgress v-if="person.goal" :goal="person.goal"/><p v-else class="person-no-goal">Сказать спасибо за хороший сервис</p>
                </button>
              </div>
              <p class="pay-safe"><ShieldCheck :size="14"/>Аккаунт гостя не нужен · демооплата</p>
            </template>
            <template v-else-if="employee">
              <button class="text-link pay-back" @click="state='choose';selectedId=''" ><ArrowLeft :size="15"/>Выбрать другого сотрудника</button>
              <div class="pay-person"><span class="avatar pay-avatar" :class="employee.color">{{ initials(employee.name) }}</span><h2>{{ employee.name }}</h2><p>{{ employee.role }}</p></div>
              <GoalProgress :goal="employee.goal"/>
              <h3 class="pay-choose">Сумма чаевых</h3>
              <div class="tip-options"><button v-for="value in presets" :key="value" @click="amount=value" :class="{selected:Number(amount)===value}">{{ money(value) }}</button></div>
              <label class="custom-amount">Или своя сумма<div><input v-model="amount" type="number" min="10" max="50000" step="1" inputmode="numeric" aria-label="Своя сумма чаевых"><span>₽</span></div></label>
              <p v-if="!amountValid" class="error-text">Введите целую сумму от 10 до 50 000 ₽.</p>
              <div class="pay-total"><span>Ваши чаевые</span><strong>{{ money(Number(amount)||0) }}</strong></div>
              <button class="btn btn-primary pay-submit" :disabled="!amountValid" @click="pay">Оплатить чаевые<ArrowRight :size="19"/></button>
              <p class="pay-safe"><ShieldCheck :size="14"/>Демо: деньги не списываются</p><button class="text-link pay-cancel" @click="state='cancelled'">Отменить</button>
            </template>
          </template>
          <div v-else-if="state==='processing'" class="pay-result"><div class="result-icon processing"><span class="spinner"></span></div><h2>Обработка платежа</h2><p>Обрабатываем демоплатёж {{ money(amount) }}.<br>Это займёт пару секунд.</p><button class="btn btn-outline full" @click="cancel" :disabled="cancelling">{{ cancelling?'Отменяем…':'Отменить оплату' }}</button></div>
          <div v-else-if="state==='success'" class="pay-result"><div class="result-icon success"><Check :size="38"/></div><h2>Чаевые отправлены</h2><p>{{ employee?.name }} · {{ money(paid?.amount) }}.</p><p v-if="paid?.goalId" class="small-text">Платёж учтён в текущей цели сотрудника.</p><div class="payment-receipt"><span>Демоплатёж</span><strong>{{ money(paid?.amount) }}</strong><span>Статус</span><span class="status success">Успешно</span></div><p class="muted small-text">Деньги не списывались. Платёж доступен в статистике сотрудника и ресторана.</p><button class="btn btn-primary full" @click="retry">Вернуться к команде<Heart :size="17"/></button><RouterLink v-if="store.session?.role==='merchant' && store.session.merchantId===data?.merchant.id" to="/app/payments" class="text-link pay-cancel">Статистика мерчанта<ArrowRight :size="15"/></RouterLink></div>
          <div v-else class="pay-result"><div class="result-icon" :class="state==='cancelled'?'neutral':'warning'"><X v-if="state==='cancelled'" :size="34"/><AlertCircle v-else :size="34"/></div><h2>{{ state==='cancelled'?'Оплата отменена':state==='declined'?'Не получилось оплатить':state==='invalid'?'QR-код недействителен':'Что-то пошло не так' }}</h2><p>{{ state==='cancelled'?'Вы отменили оплату. Деньги не списывались.':state==='declined'?'Демобанк отклонил платёж. Вы можете попробовать снова.':error }}</p><p v-if="state==='invalid'" class="muted small-text">Попросите ресторан показать действующий QR-код.</p><button v-if="data" class="btn btn-primary full" @click="retry"><RotateCcw :size="17"/>Вернуться к ресторану</button><RouterLink v-else to="/" class="btn btn-outline full">На главную</RouterLink></div>
        </section>
        <details class="demo-controls"><summary>Настройки демооплаты</summary><label>Сценарий оплаты<select v-model="scenario" @change="scenarioChange" :disabled="loading || state==='processing'"><option value="success">Успешная оплата</option><option value="declined">Отказ банка</option><option value="invalid">Недействительный QR</option><option value="cancelled">Отмена платежа</option></select></label><p>QR ресторана многоразовый. Отказ и отмена сохраняются в истории, но не увеличивают чаевые и прогресс цели.</p></details>
      </div>
    </div><footer class="pay-footer">Работает на <strong>tipro.</strong><span>Демонстрационная оплата</span></footer>
  </main>
</template>
