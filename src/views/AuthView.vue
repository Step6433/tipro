<script setup>
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { computed, reactive, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Eye, EyeOff } from 'lucide-vue-next'
import BrandLogo from '../components/BrandLogo.vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { homeForRole } from '../utils/roles'
const route=useRoute(), router=useRouter(), store=useAppStore()
const isRegister=computed(()=>route.path==='/register')
const form=reactive({role:'merchant',name:'',restaurantName:'',email:'',password:'',confirm:'',invite:''})
const error=ref(''), busy=ref(false), show=ref(false), invitation=ref(null), inviteError=ref(''), checkingInvite=ref(false)
const capabilities=ref({adminRegistration:false})
onMounted(async()=>{try{capabilities.value=await api.capabilities()}catch(e){error.value=e.message}})
let checkVersion=0
function tokenFrom(value) {
  const text=value.trim()
  try { const url=new URL(text); return url.searchParams.get('invite') || (url.pathname.startsWith('/employee/') ? url.pathname.split('/').at(-1) : text) } catch { return text }
}
async function checkInvite() {
  const version=++checkVersion; invitation.value=null; inviteError.value=''; checkingInvite.value=false
  if (!form.invite.trim()) return
  checkingInvite.value=true
  try { const data=await api.invitation(tokenFrom(form.invite)); if(version===checkVersion){invitation.value=data;if(!form.name)form.name=data.name} }
  catch(e){if(version===checkVersion)inviteError.value=e.message}
  finally{if(version===checkVersion)checkingInvite.value=false}
}
watch(()=>[route.path,route.query.role,route.query.invite],()=>{
  error.value='';form.password='';form.confirm=''
  if(['employee','merchant','admin'].includes(route.query.role))form.role=route.query.role
  form.invite=typeof route.query.invite==='string'?route.query.invite:''
  invitation.value=null;inviteError.value='';checkVersion++
  if(isRegister.value&&form.role==='employee'&&form.invite)checkInvite()
},{immediate:true})
watch(()=>form.role,()=>{error.value='';inviteError.value='';if(form.role==='employee'&&form.invite)checkInvite()})
async function submit(){
  error.value=''
  if(isRegister.value&&form.password!==form.confirm){error.value='Пароли не совпадают.';return}
  busy.value=true
  try{
    await store.authenticate(isRegister.value?'register':'login',{...form,invite:tokenFrom(form.invite)})
    const target=typeof route.query.redirect==='string'?router.resolve(route.query.redirect):null
    const allowed=target?.meta.auth&&target.meta.roles?.includes(store.session.role)
    router.push(allowed?target.fullPath:homeForRole(store.session.role))
  }catch(e){error.value=e.message}finally{busy.value=false}
}
</script>
<template>
  <main class="auth-page">
    <header class="auth-header"><BrandLogo/><LanguageSwitcher/><RouterLink to="/" class="text-link"><ArrowLeft :size="15"/>{{ $t('На главную') }}</RouterLink></header>
    <section class="auth-card">
      <h1>{{ isRegister?$t('Создать аккаунт'):$t('Вход в Tipro') }}</h1><p class="muted">{{ isRegister?$t('Выберите роль и заполните данные.'):$t('Введите email и пароль своего аккаунта.') }}</p>
      <form class="form-stack" @submit.prevent="submit">
        <template v-if="isRegister">
          <label>{{ $t('Роль') }}<select v-model="form.role"><option value="employee">{{ $t('Сотрудник') }}</option><option value="merchant">{{ $t('Администратор ресторана') }}</option><option value="admin" :disabled="!capabilities.adminRegistration">{{ $t('Администратор платформы') }}</option></select></label>
          <div class="role-description" v-if="form.role==='employee'">{{ $t('Код выдаёт администратор вашего ресторана. Это приглашение в команду, а не QR-код ресторана.') }}</div>
          <div class="role-description" v-else-if="form.role==='merchant'">{{ $t('Ресторан начнёт работу после подтверждения администратора платформы.') }}</div>
          <div class="role-description" v-else>{{ $t('Обзор всех ресторанов и платежей.') }} {{ capabilities.adminRegistration?$t('Самостоятельная регистрация разрешена в этой демонстрации.'):$t('Для входа используйте выданный аккаунт администратора платформы. Самостоятельная регистрация закрыта.') }}</div>
          <template v-if="form.role==='employee'"><div class="invitation-help"><strong>{{ $t('Где взять код?') }}</strong><ol><li>{{ $t('Администратор входит в аккаунт с ролью «Администратор ресторана».') }}</li><li>{{ $t('Открывает «Команда», добавляет вас и нажимает «Приглашение сотрудника».') }}</li><li>{{ $t('Передаёт вам код или ссылку. При открытии ссылки поле заполнится автоматически.') }}</li></ol><p>{{ $t('Если аккаунта ресторана ещё нет,') }} <RouterLink to="/register?role=merchant">{{ $t('сначала зарегистрируйте ресторан') }}</RouterLink>{{ $t('. Если он уже есть —') }} <RouterLink :to="{path:'/login',query:{redirect:'/app/employees'}}">{{ $t('войдите как администратор ресторана') }}</RouterLink>.</p></div><label>{{ $t('Код или ссылка приглашения') }}<input v-model="form.invite" required :placeholder="$t('Вставьте ссылку или код приглашения')" @input="invitation=null;inviteError='';checkingInvite=false;checkVersion++" @blur="checkInvite"></label><p v-if="checkingInvite" class="muted small-text">{{ $t('Проверяем приглашение…') }}</p><p v-if="invitation" class="invite-details">{{ invitation.restaurantName }} · {{ invitation.name }} · {{ $t(invitation.position) }}</p><p v-if="inviteError" class="error-text" role="alert">{{ $t(inviteError) }}</p></template>
          <label>{{ $t('Ваше имя') }}<input v-model="form.name" required minlength="2" maxlength="100" autocomplete="name" :placeholder="$t('Имя и фамилия')"></label>
          <label v-if="form.role==='merchant'">{{ $t('Название ресторана') }}<input v-model="form.restaurantName" required minlength="2" maxlength="100" autocomplete="organization" :placeholder="$t('Название заведения')"></label>
        </template>
        <label>{{ isRegister?'Email':$t('Email или логин') }}<input v-model="form.email" required :type="isRegister?'email':'text'" autocomplete="username" placeholder="name@example.ru"></label>
        <label>{{ $t('Пароль') }}<div class="password-input"><input v-model="form.password" required :minlength="isRegister?8:1" :type="show?'text':'password'" :autocomplete="isRegister?'new-password':'current-password'" :placeholder="isRegister?$t('Минимум 8 символов'):$t('Ваш пароль')"><button class="icon-btn" type="button" @click="show=!show" :aria-label="show?$t('Скрыть пароль'):$t('Показать пароль')"><component :is="show?EyeOff:Eye" :size="18"/></button></div></label>
        <label v-if="isRegister">{{ $t('Повторите пароль') }}<input v-model="form.confirm" required minlength="8" type="password" autocomplete="new-password" :placeholder="$t('Повторите пароль')"></label>
        <p v-if="error" class="error-text" role="alert">{{ $t(error) }}</p>
        <button class="btn btn-primary full" :disabled="busy||(isRegister&&form.role==='admin'&&!capabilities.adminRegistration)">{{ busy?$t('Подождите…'):isRegister?$t('Создать аккаунт'):$t('Войти') }}</button>
      </form>
      <p class="auth-switch">{{ isRegister?$t('Уже есть аккаунт?'):$t('Нет аккаунта?') }} <RouterLink :to="isRegister?'/login':'/register'">{{ isRegister?$t('Войти'):$t('Зарегистрироваться') }}</RouterLink></p>
      <p class="auth-note">{{ $t('Используйте тестовые данные. Аккаунт гостя для оплаты не нужен.') }}</p>
    </section>
  </main>
</template>
