import { ref } from 'vue'
import en from './en.json'
import zh from './zh.json'

export const languages = { ru: 'Русский', en: 'English', zh: '中文' }
export const numberLocales = { ru: 'ru-RU', en: 'en-US', zh: 'zh-CN' }
function savedLanguage() { if (typeof window === 'undefined') return null; try { return globalThis.localStorage?.getItem('tipro-language') } catch { return null } }
const saved = savedLanguage()
export const locale = ref(Object.hasOwn(languages, saved) ? saved : 'ru')
export function setLocale(value, persist = true) {
  if (!Object.hasOwn(languages, value)) return
  locale.value = value
  if (typeof document !== 'undefined') document.documentElement.lang = value
  if (persist) { try { globalThis.localStorage?.setItem('tipro-language', value) } catch { /* Storage is optional. */ } }
}
export function applyRestaurantLanguage(value) {
  if (!savedLanguage()) setLocale(value?.split('-')[0], false)
}
export function t(message, parameters = {}) {
  const precision = typeof message === 'string' && message.match(/^Для ([A-Z]{3}) допустимо знаков после запятой: (\d+)\.$/)
  if (precision) { message = 'Для {currency} допустимо знаков после запятой: {digits}.'; parameters = { currency: precision[1], digits: precision[2] } }
  const catalog = locale.value === 'en' ? en : locale.value === 'zh' ? zh : null
  const translation = catalog && Object.hasOwn(catalog, message) ? catalog[message] : message ?? ''
  return String(translation).replace(/\{([^}]+)\}/g, (match, key) => parameters[key] ?? match)
}
export default { install(app) { app.config.globalProperties.$t = t; setLocale(locale.value, false) } }
