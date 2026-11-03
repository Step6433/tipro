<script setup>
import { computed, reactive, ref, watch } from 'vue'
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
    <header class="auth-header"><BrandLogo/><RouterLink to="/" class="text-link"><ArrowLeft :size="15"/>На главную</RouterLink></header>
    <section class="auth-card">
      <h1>{{ isRegister?'Создать аккаунт':'Вход в Tipro' }}</h1><p class="muted">{{ isRegister?'Выберите роль и заполните данные.':'Введите email и пароль своего аккаунта.' }}</p>
      <form class="form-stack" @submit.prevent="submit">
        <template v-if="isRegister">
          <label>Роль<select v-model="form.role"><option value="employee">Сотрудник</option><option value="merchant">Администратор ресторана</option><option value="admin">Администратор платформы</option></select></label>
          <div class="role-description" v-if="form.role==='employee'">Код выдаёт администратор вашего ресторана. Это приглашение в команду, а не QR-код с чека.</div>
          <div class="role-description" v-else-if="form.role==='merchant'">Команда, QR-коды и вся статистика вашего ресторана.</div>
          <div class="role-description" v-else>Обзор всех ресторанов и платежей. Регистрация этой роли открыта только в учебном прототипе.</div>
          <template v-if="form.role==='employee'"><div class="invitation-help"><strong>Где взять код?</strong><ol><li>Администратор входит в аккаунт с ролью «Администратор ресторана».</li><li>Открывает «Команда», добавляет вас и нажимает «Приглашение сотрудника».</li><li>Передаёт вам код или ссылку. При открытии ссылки поле заполнится автоматически.</li></ol><p>Если аккаунта ресторана ещё нет, <RouterLink to="/register?role=merchant">сначала зарегистрируйте ресторан</RouterLink>. Если он уже есть — <RouterLink :to="{path:'/login',query:{redirect:'/app/employees'}}">войдите как администратор ресторана</RouterLink>.</p></div><label>Код или ссылка приглашения<input v-model="form.invite" required placeholder="Вставьте ссылку или код приглашения" @input="invitation=null;inviteError='';checkingInvite=false;checkVersion++" @blur="checkInvite"></label><p v-if="checkingInvite" class="muted small-text">Проверяем приглашение…</p><p v-if="invitation" class="invite-details">{{ invitation.restaurantName }} · {{ invitation.name }} · {{ invitation.position }}</p><p v-if="inviteError" class="error-text" role="alert">{{ inviteError }}</p></template>
          <label>Ваше имя<input v-model="form.name" required minlength="2" maxlength="100" autocomplete="name" placeholder="Имя и фамилия"></label>
          <label v-if="form.role==='merchant'">Название ресторана<input v-model="form.restaurantName" required minlength="2" maxlength="100" autocomplete="organization" placeholder="Название заведения"></label>
        </template>
        <label>Email<input v-model="form.email" required type="email" autocomplete="email" placeholder="name@example.ru"></label>
        <label>Пароль<div class="password-input"><input v-model="form.password" required :minlength="isRegister?8:1" :type="show?'text':'password'" :autocomplete="isRegister?'new-password':'current-password'" :placeholder="isRegister?'Минимум 8 символов':'Ваш пароль'"><button class="icon-btn" type="button" @click="show=!show" :aria-label="show?'Скрыть пароль':'Показать пароль'"><component :is="show?EyeOff:Eye" :size="18"/></button></div></label>
        <label v-if="isRegister">Повторите пароль<input v-model="form.confirm" required minlength="8" type="password" autocomplete="new-password" placeholder="Повторите пароль"></label>
        <p v-if="error" class="error-text" role="alert">{{ error }}</p>
        <button class="btn btn-primary full" :disabled="busy">{{ busy?'Подождите…':isRegister?'Создать аккаунт':'Войти' }}</button>
      </form>
      <p class="auth-switch">{{ isRegister?'Уже есть аккаунт?':'Нет аккаунта?' }} <RouterLink :to="isRegister?'/login':'/register'">{{ isRegister?'Войти':'Зарегистрироваться' }}</RouterLink></p>
      <p class="auth-note">Локальный прототип: используйте тестовые данные. Аккаунт гостя для оплаты не нужен.</p>
    </section>
  </main>
</template>
