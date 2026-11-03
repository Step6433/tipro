<script setup>defineProps({ light: Boolean })</script>
<template><RouterLink to="/" class="brand" :class="{ 'brand-light': light }" aria-label="Tipro — на главную"><span class="brand-mark">t<span>•</span></span><span>tipro<span class="brand-dot">.</span></span></RouterLink></template>
