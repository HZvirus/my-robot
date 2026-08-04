<script setup lang="ts">
import { ref } from 'vue'
import { login, setToken, getMe } from '@my-robot/api-client'

const emit = defineEmits<{ (e: 'logged-in'): void }>()

const phone = ref('13800000001')
const password = ref('123456')
const loading = ref(false)
const errorMsg = ref<string | null>(null)

async function onSubmit() {
  loading.value = true
  errorMsg.value = null
  try {
    const resp = await login({ phone: phone.value, password: password.value })
    setToken(resp.access_token)
    await getMe()
    emit('logged-in')
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.message ?? '登录失败，请检查手机号与密码'
  } finally {
    loading.value = false
  }
}

const quickAccounts = [
  { label: 'XX医院', phone: '13800000001' },
  { label: '张爷爷家', phone: '13800000002' },
]
function pick(phoneVal: string) {
  phone.value = phoneVal
}
</script>

<template>
  <div class="login">
    <div class="card">
      <h1 class="title">医院智能服务屏</h1>
      <p class="subtitle">请登录后开始服务</p>

      <div class="quick">
        <button v-for="a in quickAccounts" :key="a.phone" class="quick-btn" @click="pick(a.phone)">
          {{ a.label }}
        </button>
      </div>

      <form @submit.prevent="onSubmit">
        <label class="field">
          <span>手机号</span>
          <input v-model="phone" type="tel" placeholder="手机号" autocomplete="username" />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" type="password" placeholder="密码" autocomplete="current-password" />
        </label>
        <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
        <button class="submit" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>
      <p class="hint">种子账号：13800000001 / 123456（XX医院）</p>
    </div>
  </div>
</template>

<style scoped>
.login {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--layout-padding);
}
.card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: 32px;
  width: min(420px, 90%);
  box-shadow: 0 8px 30px rgba(30, 99, 214, 0.12);
}
.title {
  margin: 0 0 4px;
  font-size: var(--font-title);
  color: var(--color-primary);
}
.subtitle {
  margin: 0 0 20px;
  color: var(--color-text-muted);
}
.quick {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.quick-btn {
  flex: 1;
  padding: 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-primary);
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
}
.field {
  display: block;
  margin-bottom: 14px;
}
.field span {
  display: block;
  margin-bottom: 4px;
  color: var(--color-text-muted);
}
.field input {
  width: 100%;
  padding: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(0, 0, 0, 0.12);
  font-size: var(--font-base);
}
.submit {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-large);
  cursor: pointer;
}
.submit:disabled {
  opacity: 0.6;
}
.error {
  color: var(--color-danger);
  margin: 0 0 12px;
}
.hint {
  margin-top: 16px;
  color: var(--color-text-muted);
  font-size: 0.85em;
}
</style>
