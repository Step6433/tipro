import { ref } from 'vue'
import { t } from '../i18n'
export const currencies = { RUB: 2, USD: 2, EUR: 2, CNY: 2, THB: 2, SGD: 2, MYR: 2, IDR: 2, PHP: 2, VND: 0 }
const symbols = { RUB: '₽', USD: '$', EUR: '€', CNY: '¥', THB: '฿', SGD: 'S$', MYR: 'RM', IDR: 'Rp', PHP: '₱', VND: '₫' }
const names = { RUB: 'Российский рубль', USD: 'Доллар США', EUR: 'Евро', CNY: 'Китайский юань', THB: 'Тайский бат', SGD: 'Сингапурский доллар', MYR: 'Малайзийский ринггит', IDR: 'Индонезийская рупия', PHP: 'Филиппинское песо', VND: 'Вьетнамский донг' }
export const currentCurrency = ref('RUB')
export const currencyStep = currency => currencies[currency] === 0 ? '1' : '0.01'
export const currencySymbol = currency => symbols[currency] || currency
export const currencyLabel = currency => `${currency} · ${currencySymbol(currency)} · ${t(names[currency] || currency)}`
