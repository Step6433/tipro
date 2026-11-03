export const money = (value) => new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(value || 0)
export const dateTime = (value) => new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
export const initials = (name = '') => name.split(' ').slice(0, 2).map(s => s[0]).join('')
export const statusNames = { success: 'Успешно', declined: 'Отклонён', cancelled: 'Отменён' }
export function localDate(value) { const d = new Date(value); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}` }
