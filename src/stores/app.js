import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'
export const useAppStore = defineStore('app', () => {
  const session = ref(null), ready = ref(false), merchant = ref(null), employees = ref([]), qrs = ref([]), payments = ref([]), loading = ref(false), error = ref(''), toast = ref('')
  let toastTimer, pendingLoad
  const successful = computed(() => payments.value.filter(p => p.status === 'success'))
  const total = computed(() => successful.value.reduce((sum, p) => sum + p.amount, 0))
  const average = computed(() => successful.value.length ? Math.round(total.value / successful.value.length) : 0)
  const sortedPayments = computed(() => [...payments.value].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)))
  function notify(message) { toast.value = message; clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.value = '', 3500) }
  async function init() { if (!ready.value) { session.value = await api.session(); ready.value = true } }
  async function load() {
    if (pendingLoad) return pendingLoad
    loading.value = true; error.value = ''
    pendingLoad = api.workspace().then(data => { merchant.value = data.merchant; employees.value = data.employees; qrs.value = data.qrs; payments.value = data.payments }).catch(e => { error.value = e.message; throw e }).finally(() => { loading.value = false; pendingLoad = null })
    return pendingLoad
  }
  async function authenticate(method, values) { session.value = await api[method](values); await load() }
  async function demo(role = 'merchant') { session.value = await api.demo(role); await load() }
  async function logout() { await api.logout(); session.value = null; merchant.value = null; employees.value = []; payments.value = []; qrs.value = [] }
  const employeeName = id => employees.value.find(e => e.id === id)?.name || 'Сотрудник'
  return { session, ready, merchant, employees, qrs, payments, loading, error, toast, total, average, successful, sortedPayments, init, load, authenticate, demo, logout, notify, employeeName }
})
