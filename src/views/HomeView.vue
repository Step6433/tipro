<script setup>
import { ArrowRight } from 'lucide-vue-next'
import BrandLogo from '../components/BrandLogo.vue'
const accounts = [
  { role: 'employee', title: 'Сотрудникам', text: 'Личные чаевые, история платежей и цели. Регистрация по приглашению ресторана.' },
  { role: 'merchant', title: 'Ресторанам', text: 'Команда, QR-коды и статистика всех полученных чаевых.' },
  { role: 'admin', title: 'Платформе', text: 'Рестораны, сотрудники и платежи в общем кабинете администратора.' },
]
</script>
<template>
  <div class="landing">
    <header class="landing-header"><BrandLogo/><nav><RouterLink to="/login">Войти</RouterLink><RouterLink to="/register" class="btn btn-primary btn-small">Создать аккаунт</RouterLink></nav></header>
    <main class="home-main">
      <section class="home-intro">
        <div class="home-copy"><span class="section-label">Для ресторанов и их команд</span><h1>Чаевые без наличных.</h1><p>Гость сканирует QR-код ресторана, выбирает сотрудника и оставляет чаевые. Команда видит свои результаты, ресторан — общую статистику.</p><RouterLink to="/register?role=merchant" class="btn btn-primary">Подключить ресторан<ArrowRight :size="17"/></RouterLink><span class="home-caption">Гостям не нужно регистрироваться.</span></div>
        <div class="how-it-works"><h2>Как это работает</h2><ol><li><span>01</span><div><strong>Добавьте команду</strong><p>Создайте ресторан и пригласите сотрудников в личные кабинеты.</p></div></li><li><span>02</span><div><strong>Добавьте QR на чек</strong><p>Внизу чека для гостя. Код открывает страницу ресторана.</p></div></li><li><span>03</span><div><strong>Следите за результатами</strong><p>Сотрудник видит свои чаевые и цели, администратор — весь ресторан.</p></div></li></ol></div>
      </section>
      <section class="home-accounts"><div class="home-section-heading"><h2>Каждому — свой кабинет</h2><span>Доступ зависит от роли аккаунта</span></div><RouterLink v-for="a in accounts" :key="a.role" :to="{path:'/register',query:{role:a.role}}" class="account-row"><h3>{{ a.title }}</h3><p>{{ a.text }}</p><ArrowRight :size="19"/></RouterLink></section>
    </main>
    <footer class="public-footer"><span>Tipro · Онлайн-чаевые</span><span>Учебный прототип. Оплата без списания денег.</span></footer>
  </div>
</template>
