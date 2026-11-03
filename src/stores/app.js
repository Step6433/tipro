import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'
export const useAppStore = defineStore('app', () => {
  const session = ref(null), ready = ref(false), user = ref(null), merchant = ref(null)
  const employees = ref([]), qrs = ref([]), payments = ref([]), loading = ref(false), error = ref(''), toast = ref('')
  let toastTimer, pendingLoad, generation = 0
  const successful = computed(() => payments.value.filter(p => p.status === 'success'))
  const total = computed(() => successful.value.reduce((sum, p) => sum + p.amount, 0))
  const average = computed(() => successful.value.length ? Math.round(total.value / successful.value.length) : 0)
  const sortedPayments = computed(() => [...payments.value].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)))
  const self = computed(() => employees.value.find(e => e.id === session.value?.employeeId))
  function notify(message) { toast.value = message; clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.value = '', 3500) }
  function clear() { generation++; pendingLoad = null; user.value = null; merchant.value = null; employees.value = []; qrs.value = []; payments.value = []; error.value = ''; loading.value = false }
  async function init() { if (!ready.value) { session.value = await api.session(); ready.value = true } }
  async function load() {
    if (pendingLoad) return pendingLoad
    const version = generation
    loading.value = true; error.value = ''
    const request = api.workspace().then(data => {
      if (version !== generation) return
      user.value = data.user; merchant.value = data.merchant; employees.value = data.employees; qrs.value = data.qrs; payments.value = data.payments
    }).catch(e => { if (version === generation) error.value = e.message; throw e }).finally(() => {
      if (version === generation) { loading.value = false; pendingLoad = null }
    })
    pendingLoad = request
    return request
  }
  async function authenticate(method, values) { const next = await api[method](values); clear(); session.value = next; await load() }
  async function demo(role = 'merchant') { const next = await api.demo(role); clear(); session.value = next; await load() }
  async function logout() { await api.logout(); clear(); session.value = null }
  async function refreshSession() {
    const next = await api.session()
    if (next?.userId !== session.value?.userId) clear()
    session.value = next
    if (next) await load()
  }
  const employeeName = id => employees.value.find(e => e.id === id)?.name || 'Сотрудник'
  return { session, ready, user, self, merchant, employees, qrs, payments, loading, error, toast, total, average, successful, sortedPayments, init, load, authenticate, demo, logout, refreshSession, notify, employeeName }
})
