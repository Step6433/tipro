// Calendar dates are labels (YYYY-MM-DD), not UTC instants.
export const browserTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
export function calendarDate(value, timeZone = browserTimeZone()) {
  if (!value) return ''
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date)
  const part = type => parts.find(p => p.type === type).value
  return `${part('year')}-${part('month')}-${part('day')}`
}
export function shiftCalendarDate(key, days) {
  const [year, month, day] = key.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day + days))
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`
}
export function buildDailySeries({ payments = [], dailySeries = null, seriesTimeZone = null, days = 7, now = new Date(), timeZone = browserTimeZone(), locale = 'ru-RU' } = {}) {
  const today = calendarDate(now, timeZone)
  if (!today) return []
  const totals = new Map()
  const add = (key, value) => {
    const number = Number(value)
    if (key && Number.isFinite(number)) totals.set(key, (totals.get(key) || 0) + number)
  }
  if (Array.isArray(dailySeries) && seriesTimeZone === timeZone) {
    for (const row of dailySeries) add(row.date || row.period?.slice(0, 10), row.total)
  } else {
    // Already aggregated UTC days cannot be shifted: payments around midnight must be split again.
    for (const payment of payments || []) if (payment.status === 'success') add(calendarDate(payment.createdAt, timeZone), payment.amount)
  }
  const formatter = new Intl.DateTimeFormat(locale, { timeZone: 'UTC', day: 'numeric', month: 'short' })
  return Array.from({ length: days }, (_, index) => {
    const key = shiftCalendarDate(today, index - days + 1)
    const [year, month, day] = key.split('-').map(Number)
    return { key, date: formatter.format(new Date(Date.UTC(year, month - 1, day))), value: totals.get(key) || 0 }
  })
}
