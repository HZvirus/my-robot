<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { Department, TriageMessage } from '@my-robot/shared-types'
import { BaseButton, LoadingSpinner, TypewriterText } from '@my-robot/ui'
import { useTriageStore } from '@/stores/triage'

const router = useRouter()
const store = useTriageStore()

const input = ref('')
const listEl = ref<HTMLElement | null>(null)

void store.ensureDepartments()

const activeAssistantId = computed(() => {
  if (!store.streaming) return null
  for (let i = store.messages.length - 1; i >= 0; i--) {
    if (store.messages[i].role === 'assistant') return store.messages[i].id
  }
  return null
})

const quickPrompts = ['肚子疼挂什么科', '咳嗽一周了挂什么科', '医院怎么挂号', '什么情况要去急诊']

function registerActions(m: TriageMessage): Department[] {
  if (m.role !== 'assistant') return []
  const list = store.departmentsFor(m.content)
  return [...list.filter((d) => d.name === '急诊科'), ...list.filter((d) => d.name !== '急诊科')]
}

function goRegister(d: Department) {
  router.push({ path: '/register', query: { department: d.name, departmentId: d.id } })
}

function send() {
  const text = input.value.trim()
  if (!text || store.streaming) return
  input.value = ''
  store.send(text)
}

function useQuick(prompt: string) {
  input.value = prompt
  send()
}

watch(
  () => [store.messages.length, store.messages[store.messages.length - 1]?.content],
  async () => {
    await nextTick()
    listEl.value?.scrollTo({ top: listEl.value.scrollHeight })
  }
)
</script>

<template>
  <div class="triage">
    <header class="triage-header">
      <button
        class="back-btn"
        aria-label="返回"
        @click="router.push('/')"
      >
        ‹
      </button>
      <span class="triage-title">智能导诊</span>
      <span class="header-space" />
    </header>

    <div
      ref="listEl"
      class="msg-list"
    >
      <p
        v-if="store.messages.length === 0"
        class="welcome"
      >
        您好，我是智能导诊助手。描述您的症状，我会结合医院资料推荐就诊科室。
      </p>

      <div
        v-for="m in store.messages"
        :key="m.id"
        class="bubble-row"
        :class="m.role"
      >
        <div class="bubble">
          <div
            v-if="m.content"
            class="bubble-text"
          >
            <TypewriterText
              v-if="m.role === 'assistant'"
              :text="m.content"
              :active="m.id === activeAssistantId"
            />
            <template v-else>
              {{ m.content }}
            </template>
          </div>
          <LoadingSpinner
            v-if="m.role === 'assistant' && store.streaming && !m.content"
            :size="18"
          />
          <span
            v-if="m.interrupted && m.role === 'assistant'"
            class="interrupted"
          >
            （已中断）
          </span>
        </div>
        <div
          v-if="registerActions(m).length"
          class="action-row"
        >
          <button
            v-for="d in registerActions(m)"
            :key="d.name"
            class="register-btn"
            :class="{ emergency: d.name === '急诊科' }"
            @click="goRegister(d)"
          >
            {{ d.name === '急诊科' ? '前往急诊挂号' : `挂号${d.name}` }}
          </button>
          <p
            v-if="registerActions(m).some((d) => d.name === '急诊科')"
            class="emergency-hint"
          >
            病情危重请立即拨打 120
          </p>
        </div>
      </div>

      <p
        v-if="store.error"
        class="error"
      >
        {{ store.error }}
      </p>
    </div>

    <details
      v-if="store.sources.length"
      class="sources"
    >
      <summary>参考来源 ({{ store.sources.length }})</summary>
      <div
        v-for="(s, i) in store.sources"
        :key="i"
        class="source"
      >
        <span class="source-file">{{ s.file }}</span>
        <p class="source-text">
          {{ s.text }}
        </p>
      </div>
    </details>

    <div class="quick-row">
      <button
        v-for="p in quickPrompts"
        :key="p"
        class="chip"
        :disabled="store.streaming"
        @click="useQuick(p)"
      >
        {{ p }}
      </button>
    </div>

    <footer class="input-bar">
      <input
        v-model="input"
        class="input"
        :disabled="store.streaming"
        placeholder="描述您的症状…"
        @keyup.enter="send"
      >
      <BaseButton
        type="primary"
        :disabled="!input.trim() || store.streaming"
        @click="send"
      >
        {{ store.streaming ? '生成中' : '发送' }}
      </BaseButton>
    </footer>
  </div>
</template>

<style scoped>
.triage {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 720px;
  margin: 0 auto;
  background: #f5f7fa;
}

.triage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
  position: sticky;
  top: 0;
}

.back-btn {
  border: none;
  background: none;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
  color: #333;
  padding: 0 4px;
}

.triage-title {
  font-size: 16px;
  font-weight: 600;
}

.header-space {
  width: 28px;
}

.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.welcome {
  text-align: center;
  color: #999;
  font-size: 14px;
  line-height: 1.8;
  margin: 24px 16px;
}

.bubble-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin-bottom: 12px;
}

.bubble-row.user {
  align-items: flex-end;
}

.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e4e7ed;
  color: #333;
  line-height: 1.6;
  font-size: 14px;
  word-break: break-word;
  white-space: pre-wrap;
}

.bubble-row.user .bubble {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.register-btn {
  border: 1px solid #409eff;
  color: #fff;
  background: #409eff;
  border-radius: 18px;
  padding: 7px 16px;
  font-size: 13px;
  cursor: pointer;
}

.register-btn.emergency {
  border-color: #f56c6c;
  background: #f56c6c;
}

.emergency-hint {
  width: 100%;
  margin: 0;
  font-size: 12px;
  color: #f56c6c;
}

.interrupted {
  color: #c0c4cc;
  font-size: 12px;
  margin-left: 6px;
}

.error {
  color: #f56c6c;
  font-size: 13px;
  text-align: center;
  margin: 8px 0;
}

.sources {
  margin: 0 12px 8px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 8px 12px;
  max-height: 40vh;
  overflow-y: auto;
}

.sources summary {
  cursor: pointer;
  font-size: 13px;
  color: #606266;
}

.source {
  margin-top: 8px;
  border-top: 1px dashed #e4e7ed;
  padding-top: 8px;
}

.source-file {
  font-size: 12px;
  color: #409eff;
}

.source-text {
  font-size: 12px;
  color: #909399;
  margin: 4px 0 0;
  line-height: 1.5;
}

.quick-row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 8px 12px;
}

.chip {
  flex-shrink: 0;
  border: 1px solid #409eff;
  color: #409eff;
  background: #fff;
  border-radius: 16px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}

.chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-bar {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1px solid #eee;
}

.input {
  flex: 1;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
}

.input:focus {
  border-color: #409eff;
}
</style>
