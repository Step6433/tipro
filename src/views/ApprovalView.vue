<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Clock, LogOut } from 'lucide-vue-next'
import BrandLogo from '../components/BrandLogo.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { useAppStore } from '../stores/app'
const store=useAppStore(),router=useRouter(),busy=ref(false),error=ref('')
let timer
async function check(){
  if(busy.value)return
  busy.value=true;error.value=''
  try{
    await store.refreshSession()
    if(!store.session)router.replace('/login')
    else if(!store.awaitingApproval)router.replace('/app')
  }catch(e){error.value=e.message}
  finally{busy.value=false}
}
async function logout(){try{await store.logout();router.replace('/login')}catch(e){error.value=e.message}}
onMounted(()=>{timer=window.setInterval(()=>{if(document.visibilityState==='visible')check()},5000)})
onUnmounted(()=>clearInterval(timer))
</script>
<template>
  <main class="auth-page"><header class="auth-header"><BrandLogo/><LanguageSwitcher/></header>
    <section class="auth-card approval-wait"><Clock :size="40"/><h1>{{ $t('Ресторан ожидает подтверждения') }}</h1><p><strong>{{ store.session?.merchantName }}</strong></p><p>{{ $t('Заявка отправлена администратору платформы. После одобрения откроется доступ к сотрудникам, QR-кодам и чаевым.') }}</p><p class="muted small-text">{{ $t('Статус обновляется автоматически. Самостоятельная активация недоступна.') }}</p><p v-if="error" class="error-text" role="alert">{{ $t(error) }}</p><button class="btn btn-primary full" :disabled="busy" @click="check">{{ busy?$t('Проверяем…'):$t('Проверить статус') }}</button><button class="text-link" @click="logout"><LogOut :size="16"/>{{ $t('Выйти из аккаунта') }}</button></section>
  </main>
</template>
