<script setup>import BrandLogo from '../components/BrandLogo.vue'</script>
<template><main class="not-found"><BrandLogo/><span class="error-number">404</span><h1>{{ $t('Кажется, вы свернули не туда.') }}</h1><p class="muted">{{ $t('Здесь пока нет страницы, но есть путь к хорошему сервису.') }}</p><RouterLink to="/" class="btn btn-primary">{{ $t('На главную') }}</RouterLink></main></template>
