import { calendarDate } from './dates'
import { currentCurrency, currencies, currencySymbol } from './currency'
import { locale, numberLocales, t } from '../i18n'
export const money = (value, currency = currentCurrency.value) => new Intl.NumberFormat(numberLocales[locale.value], { style: 'currency', currency, minimumFractionDigits: 0, maximumFractionDigits: currencies[currency] ?? 2 }).formatToParts(value || 0).map(part => part.type === 'currency' ? currencySymbol(currency) : part.value).join('')
export const dateTime = value => value ? new Intl.DateTimeFormat(numberLocales[locale.value], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : t('Дата не указана')
export const initials = (name = '') => name.split(' ').filter(Boolean).slice(0, 2).map(s => s[0]).join('')
export const statusNames = { created: 'Создан', success: 'Успешно', declined: 'Отклонён', cancelled: 'Отменён', pending: 'Ожидает' }
export const localDate = value => calendarDate(value)
