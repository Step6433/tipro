<script setup>
import { ref } from 'vue'
import { Plus, Pencil, Target, Check } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { currencyStep } from '../utils/currency'
import BaseModal from '../components/BaseModal.vue'
import GoalProgress from '../components/GoalProgress.vue'
const store=useAppStore(),editing=ref(null),busy=ref(false),error=ref(''),pageError=ref('')
function edit(goal){error.value='';editing.value=goal?{id:goal.id,title:goal.title,target:goal.target,currency:goal.currency}:{title:'',target:'',currency:store.merchant?.currency||store.currency}}
async function save(){busy.value=true;error.value='';try{await api.saveGoal(store.session.employeeId,editing.value);await store.load();editing.value=null;store.notify('Цель сохранена')}catch(e){error.value=e.message}finally{busy.value=false}}
async function activate(goal){busy.value=true;pageError.value='';try{await api.activateGoal(store.session.employeeId,goal.id);await store.load();store.notify('Текущая цель изменена')}catch(e){pageError.value=e.message}finally{busy.value=false}}
</script>
<template>
  <div class="page-heading"><div><h1>{{ $t('Мои цели') }}</h1><p>{{ $t('Гости видят текущую цель. Успешные чаевые увеличивают её прогресс.') }}</p></div><button class="btn btn-primary" @click="edit()"><Plus :size="17"/>{{ $t('Добавить цель') }}</button></div>
  <p v-if="pageError" class="error-banner" role="alert">{{ $t(pageError) }}</p>
  <div v-if="!store.self?.goals.length" class="panel empty"><Target :size="30"/><h3>{{ $t('Целей пока нет') }}</h3><p>{{ $t('Например, на обучение, поездку или новую гитару.') }}</p><button class="btn btn-outline" @click="edit()">{{ $t('Добавить первую цель') }}</button></div>
  <div class="goals-grid"><article v-for="goal in store.self?.goals" :key="goal.id" class="panel goal-card"><div class="goal-card-head"><span class="status" :class="store.self.activeGoalId===goal.id?'success':'cancelled'">{{ store.self.activeGoalId===goal.id?$t('Текущая цель'):$t('Неактивная цель') }}</span><button class="icon-btn" @click="edit(goal)" :aria-label="$t('Редактировать цель {0}', {0: goal.title})"><Pencil :size="16"/></button></div><GoalProgress :goal="goal"/><button v-if="store.self.activeGoalId!==goal.id" class="btn btn-outline btn-small full" :disabled="busy" @click="activate(goal)">{{ $t('Сделать текущей') }}</button><p v-else class="goal-current"><Check :size="15"/>{{ $t('Показывается гостям ресторана') }}</p></article></div>
  <BaseModal v-if="editing" :title="editing.id?$t('Редактировать цель'):$t('Новая цель')" @close="!busy&&(editing=null)"><form class="form-stack" @submit.prevent="save"><label>{{ $t('На что копите?') }}<input v-model="editing.title" required maxlength="100" :placeholder="$t('Например, на путешествие')"></label><label>{{ $t('Нужная сумма') }}<input v-model="editing.target" required type="number" :min="currencyStep(editing.currency)" max="10000000" :step="currencyStep(editing.currency)" inputmode="numeric" placeholder="50000"></label><p class="muted small-text">{{ $t('Новая цель станет текущей. Собранные суммы у прежних целей сохранятся. При редактировании прогресс не сбрасывается.') }}</p><p v-if="error" class="error-text" role="alert">{{ $t(error) }}</p><button class="btn btn-primary" :disabled="busy">{{ busy?$t('Сохраняем…'):$t('Сохранить') }}</button></form></BaseModal>
</template>
