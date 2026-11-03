<script setup>
import { ref } from 'vue'
import { Plus, Pencil, Target, Check } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import BaseModal from '../components/BaseModal.vue'
import GoalProgress from '../components/GoalProgress.vue'
const store=useAppStore(),editing=ref(null),busy=ref(false),error=ref(''),pageError=ref('')
function edit(goal){error.value='';editing.value=goal?{id:goal.id,title:goal.title,target:goal.target}:{title:'',target:''}}
async function save(){busy.value=true;error.value='';try{await api.saveGoal(store.session.employeeId,editing.value);await store.load();editing.value=null;store.notify('Цель сохранена')}catch(e){error.value=e.message}finally{busy.value=false}}
async function activate(goal){busy.value=true;pageError.value='';try{await api.activateGoal(store.session.employeeId,goal.id);await store.load();store.notify('Текущая цель изменена')}catch(e){pageError.value=e.message}finally{busy.value=false}}
</script>
<template>
  <div class="page-heading"><div><h1>Мои цели</h1><p>Гости видят текущую цель. Успешные чаевые увеличивают её прогресс.</p></div><button class="btn btn-primary" @click="edit()"><Plus :size="17"/>Добавить цель</button></div>
  <p v-if="pageError" class="error-banner" role="alert">{{ pageError }}</p>
  <div v-if="!store.self?.goals.length" class="panel empty"><Target :size="30"/><h3>Целей пока нет</h3><p>Например, на обучение, поездку или новую гитару.</p><button class="btn btn-outline" @click="edit()">Добавить первую цель</button></div>
  <div class="goals-grid"><article v-for="goal in store.self?.goals" :key="goal.id" class="panel goal-card"><div class="goal-card-head"><span class="status" :class="store.self.activeGoalId===goal.id?'success':'cancelled'">{{ store.self.activeGoalId===goal.id?'Текущая цель':'Неактивная цель' }}</span><button class="icon-btn" @click="edit(goal)" :aria-label="`Редактировать цель ${goal.title}`"><Pencil :size="16"/></button></div><GoalProgress :goal="goal"/><button v-if="store.self.activeGoalId!==goal.id" class="btn btn-outline btn-small full" :disabled="busy" @click="activate(goal)">Сделать текущей</button><p v-else class="goal-current"><Check :size="15"/>Показывается гостям ресторана</p></article></div>
  <BaseModal v-if="editing" :title="editing.id?'Редактировать цель':'Новая цель'" @close="!busy&&(editing=null)"><form class="form-stack" @submit.prevent="save"><label>На что копите?<input v-model="editing.title" required maxlength="100" placeholder="Например, на путешествие"></label><label>Нужная сумма, ₽<input v-model="editing.target" required type="number" min="100" max="10000000" step="1" inputmode="numeric" placeholder="50000"></label><p class="muted small-text">Новая цель станет текущей. Собранные суммы у прежних целей сохранятся. При редактировании прогресс не сбрасывается.</p><p v-if="error" class="error-text" role="alert">{{ error }}</p><button class="btn btn-primary" :disabled="busy">{{ busy?'Сохраняем…':'Сохранить' }}</button></form></BaseModal>
</template>
