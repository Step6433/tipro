<script setup>
import { locale, languages, setLocale } from '../i18n'
</script>
<template>
  <label class="language-switch"><span class="sr-only">{{ $t('Язык интерфейса') }}</span><select :value="locale" @change="setLocale($event.target.value)" :aria-label="$t('Язык интерфейса')"><option v-for="(name,code) in languages" :key="code" :value="code">{{ name }}</option></select></label>
</template>
