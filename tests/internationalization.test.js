import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp, h } from 'vue'
import { createPinia } from 'pinia'
import { renderToString } from '@vue/server-renderer'

const vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
after(() => vite.close())
const i18n = await vite.ssrLoadModule('/src/i18n/index.js')
const { money, dateTime } = await vite.ssrLoadModule('/src/utils/format.js')
const { currencyLabel, currencies } = await vite.ssrLoadModule('/src/utils/currency.js')

test('international currencies have symbols and localized names', () => {
  i18n.setLocale('en', false)
  for (const [code, symbol] of [['USD', '$'], ['EUR', '€'], ['CNY', '¥']]) {
    assert.equal(currencies[code], 2)
    assert.ok(money(12.35, code).includes(symbol))
    assert.ok(currencyLabel(code).includes(symbol))
  }
  assert.ok(currencyLabel('CNY').includes('Chinese yuan'))
  i18n.setLocale('zh', false)
  assert.ok(currencyLabel('CNY').includes('人民币'))
  i18n.setLocale('ru', false)
  assert.ok(currencyLabel('USD').includes('Доллар США'))
})

test('language changes messages, dates and numeric conventions without changing stored amounts', () => {
  i18n.setLocale('en', false)
  assert.equal(i18n.t('Спасибо за чаевые!'), 'Thank you for your tip!')
  assert.ok(money(12.35, 'EUR').includes('12.35'))
  assert.ok(dateTime('2026-01-02T10:00:00Z').includes('Jan'))
  i18n.setLocale('ru', false)
  assert.ok(money(12.35, 'EUR').includes('12,35'))
  i18n.setLocale('zh', false)
  assert.equal(i18n.t('Вы отправили {amount} сотруднику {name}.', { amount: '¥10', name: 'Anna' }), '您已向 Anna 支付 ¥10。')
  i18n.setLocale('unsupported', false)
  assert.equal(i18n.locale.value, 'zh')
})

test('landing page actually renders English and Chinese translations', async () => {
  const { default: Home } = await vite.ssrLoadModule('/src/views/HomeView.vue')
  function makeApp() {
    return createSSRApp(Home).use(createPinia()).use(i18n.default).component('RouterLink', { setup(_, { slots }) { return () => h('a', {}, slots.default?.()) } })
  }
  i18n.setLocale('en', false)
  const english = await renderToString(makeApp())
  assert.ok(english.includes('Cashless tips.'))
  assert.ok(english.includes('Create account'))
  assert.ok(!english.includes('Чаевые без наличных'))
  i18n.setLocale('zh', false)
  const chinese = await renderToString(makeApp())
  assert.ok(chinese.includes('无现金小费。'))
  assert.ok(chinese.includes('创建账户'))
  assert.ok(chinese.includes('个人小费、付款记录和目标'))
})
