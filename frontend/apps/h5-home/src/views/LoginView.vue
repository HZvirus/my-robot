<script setup lang="ts">
import { ref } from 'vue'
import { login, setToken, getMe } from '@my-robot/api-client'

const emit = defineEmits<{ (e: 'logged-in'): void }>()

const phone = ref('13800000002')
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
    errorMsg.value = e?.response?.data?.message ?? '登录失败'
  } finally {
    loading.value = false
  }
}

function pick(p: string) {
  phone.value = p
}
</script>

<template>
  <div class="login">
    <div class="card">
      <div class="avatar">🤖</div>
      <h1 class="title">家庭照护小助手</h1>
      <p class="subtitle">爷爷您好，请先登录</p>

      <div class="quick">
        <button class="quick-btn" @click="pick('13800000002')">张爷爷家</button>
        <button class="quick-btn" @click="pick('13800000001')">XX医院</button>
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
      <p class="hint">种子账号：13800000002 / 123456（张爷爷家）</p>
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
  padding: 28px;
  width: min(440px, 92%);
  box-shadow: 0 8px 30px rgba(245, 158, 60, 0.18);
  text-align: center;
}
.avatar {
  font-size: 56px;
}
.title {
  margin: 8px 0 4px;
  font-size: var(--font-title);
  color: var(--color-primary-dark);
}
.subtitle {
  margin: 0 0 18px;
  color: var(--color-text-muted);
}
.quick {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.quick-btn {
  flex: 1;
  padding: 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-primary);
  background: transparent;
  color: var(--color-primary-dark);
  cursor: pointer;
  font-size: 1em;
}
.field {
  display: block;
  margin-bottom: 14px;
  text-align: left;
}
.field span {
  display: block;
  margin-bottom: 4px;
  color: var(--color-text-muted);
}
.field input {
  width: 100%;
  padding: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(0, 0, 0, 0.12);
  font-size: var(--font-base);
}
.submit {
  width: 100%;
  padding: 16px;
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
}
.hint {
  margin-top: 14px;
  color: var(--color-text-muted);
  font-size: 0.85em;
}
</style>
