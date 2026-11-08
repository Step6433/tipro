<script setup>
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import { homeForRole } from '../utils/roles'
import { ArrowRight } from 'lucide-vue-next'
import BrandLogo from '../components/BrandLogo.vue'
const store = useAppStore()
const dashboard = computed(() => store.awaitingApproval ? '/approval' : homeForRole(store.session?.role))
const accounts = [
  { role: 'employee', title: 'Сотрудникам', text: 'Личные чаевые, история платежей и цели. Регистрация по приглашению ресторана.' },
  { role: 'merchant', title: 'Ресторанам', text: 'Команда, QR-коды и статистика всех полученных чаевых.' },
  { role: 'admin', title: 'Платформе', text: 'Рестораны, сотрудники и платежи в общем кабинете администратора.' },
]
</script>
<template>
  <div class="landing">
    <header class="landing-header"><BrandLogo/><nav><LanguageSwitcher/><RouterLink v-if="store.session" :to="dashboard" class="btn btn-primary btn-small">{{ $t('Вернуться в кабинет') }}</RouterLink><template v-else><RouterLink to="/login">{{ $t('Войти') }}</RouterLink><RouterLink to="/register" class="btn btn-primary btn-small">{{ $t('Создать аккаунт') }}</RouterLink></template></nav></header>
    <main class="home-main">
      <section class="home-intro">
        <div class="home-copy"><span class="section-label">{{ $t('Для ресторанов и их команд') }}</span><h1>{{ $t('Чаевые без наличных.') }}</h1><p>{{ $t('Гость сканирует QR-код сотрудника и оставляет чаевые. Команда видит свои результаты, ресторан — общую статистику.') }}</p><RouterLink :to="store.session ? dashboard : '/register?role=merchant'" class="btn btn-primary">{{ store.session ? $t('Вернуться в кабинет') : $t('Подключить ресторан') }}<ArrowRight :size="17"/></RouterLink><span class="home-caption">{{ $t('Гостям не нужно регистрироваться.') }}</span></div>
        <div class="how-it-works"><h2>{{ $t('Как это работает') }}</h2><ol><li><span>01</span><div><strong>{{ $t('Добавьте команду') }}</strong><p>{{ $t('Создайте ресторан и пригласите сотрудников в личные кабинеты.') }}</p></div></li><li><span>02</span><div><strong>{{ $t('Создайте QR сотрудника') }}</strong><p>{{ $t('Выберите сотрудника и скачайте одноразовый QR. Код действует 24 часа.') }}</p></div></li><li><span>03</span><div><strong>{{ $t('Следите за результатами') }}</strong><p>{{ $t('Сотрудник видит свои чаевые и цели, администратор — весь ресторан.') }}</p></div></li></ol></div>
      </section>
      <section v-if="!store.session" class="home-accounts"><div class="home-section-heading"><h2>{{ $t('Каждому — свой кабинет') }}</h2><span>{{ $t('Доступ зависит от роли аккаунта') }}</span></div><RouterLink v-for="a in accounts" :key="a.role" :to="{path:'/register',query:{role:a.role}}" class="account-row"><h3>{{ $t(a.title) }}</h3><p>{{ $t(a.text) }}</p><ArrowRight :size="19"/></RouterLink></section>
    </main>
    <footer class="public-footer"><span>{{ $t('Tipro · Онлайн-чаевые') }}</span><span>{{ $t('Учебный прототип. Оплата без списания денег.') }}</span></footer>
  </div>
</template>
