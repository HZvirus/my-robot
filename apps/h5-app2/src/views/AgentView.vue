<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BaseButton, LoadingSpinner } from '@my-robot/ui'
import { useAgentStore } from '@/stores/agent'

const router = useRouter()
const store = useAgentStore()

const input = ref('')
const listEl = ref<HTMLElement | null>(null)
const expandedSteps = ref<Set<string>>(new Set())

const quickPrompts = ['现在几点?', '帮我计算 (12+8)*3', '你好,介绍一下你自己']

function toggleSteps(id: string) {
  if (expandedSteps.value.has(id)) {
    expandedSteps.value.delete(id)
  } else {
    expandedSteps.value.add(id)
  }
}

function parseAction(action: string): { tool: string; args: string } {
  try {
    const parsed = JSON.parse(action) as { tool?: string; args?: unknown }
    return { tool: parsed.tool ?? action, args: JSON.stringify(parsed.args ?? {}, null, 2) }
  } catch {
    return { tool: action, args: '' }
  }
}

function send() {
  const text = input.value.trim()
  if (!text || store.running) return
  input.value = ''
  store.send(text)
}

function useQuick(prompt: string) {
  input.value = prompt
  send()
}

function newChat() {
  store.reset()
  input.value = ''
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
  <div class="chat">
    <header class="chat-header">
      <button
        class="back-btn"
        aria-label="返回"
        @click="router.push('/')"
      >
        ‹
      </button>
      <div class="header-title">
        <span class="avatar">A</span>
        <div class="title-text">
          <span class="chat-title">智能助手 · Agent</span>
          <span class="chat-subtitle">推理工具模式 · 非流式</span>
        </div>
      </div>
      <div class="header-actions">
        <button
          class="new-btn"
          :disabled="store.running"
          @click="newChat"
        >
          新对话
        </button>
      </div>
    </header>

    <div
      ref="listEl"
      class="msg-list"
    >
      <p
        v-if="store.messages.length === 0"
        class="welcome"
      >
        你好，我是智能助手。当你需要时间、计算等外部信息时，我会自动调用
        工具获取结果，再结合工具返回的数据作答。
      </p>

      <div
        v-for="m in store.messages"
        :key="m.id"
        class="bubble-row"
        :class="m.role"
      >
        <span
          v-if="m.role === 'assistant'"
          class="bubble-avatar"
        >A</span>
        <div class="bubble">
          <div
            v-if="m.content"
            class="bubble-text"
          >
            {{ m.content }}
          </div>
          <LoadingSpinner
            v-if="m.role === 'assistant' && store.running && !m.content"
            :size="18"
          />
          <span
            v-if="m.role === 'assistant' && store.running && !m.content"
            class="thinking"
          >
            正在推理…
          </span>

          <button
            v-if="m.role === 'assistant' && m.steps.length > 0"
            class="steps-toggle"
            @click="toggleSteps(m.id)"
          >
            {{ expandedSteps.has(m.id) ? '收起' : '展开' }}推理过程 ({{ m.steps.length }} 步)
          </button>

          <div
            v-if="m.role === 'assistant' && expandedSteps.has(m.id)"
            class="steps-panel"
          >
            <div
              v-for="s in m.steps"
              :key="s.stepNo"
              class="step"
            >
              <div class="step-header">
                <span class="step-no">STEP {{ s.stepNo + 1 }}</span>
                <span class="step-tool">{{ parseAction(s.action).tool }}</span>
                <span
                  class="step-status"
                  :class="s.status"
                >
                  {{ s.status }}
                </span>
              </div>
              <p
                v-if="s.thought"
                class="step-thought"
              >
                {{ s.thought }}
              </p>
              <p
                v-if="parseAction(s.action).args"
                class="step-args"
              >
                {{ parseAction(s.action).args }}
              </p>
              <pre class="step-obs">{{ s.observation }}</pre>
            </div>
          </div>
        </div>
      </div>

      <p
        v-if="store.error"
        class="error"
      >
        {{ store.error }}
      </p>
    </div>

    <div
      v-if="store.messages.length === 0"
      class="quick-row"
    >
      <button
        v-for="p in quickPrompts"
        :key="p"
        class="chip"
        :disabled="store.running"
        @click="useQuick(p)"
      >
        {{ p }}
      </button>
    </div>

    <footer class="input-bar">
      <input
        v-model="input"
        class="input"
        :disabled="store.running"
        placeholder="问点什么，试试时间或计算…"
        @keyup.enter="send"
      >
      <BaseButton
        type="primary"
        :disabled="!input.trim() || store.running"
        @click="send"
      >
        {{ store.running ? '推理中' : '发送' }}
      </BaseButton>
    </footer>

    <p class="disclaimer">
      智能助手可调用时间与计算工具，不提供医疗诊断。如有紧急症状请立即就医。
    </p>
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 720px;
  margin: 0 auto;
  background: linear-gradient(180deg, #eaf6ef 0%, #f5f7fa 160px);
}

.chat-header {
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

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.title-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
  min-width: 0;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-subtitle {
  font-size: 11px;
  color: #909399;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.new-btn {
  border: 1px solid #409eff;
  color: #409eff;
  background: #fff;
  border-radius: 16px;
  padding: 4px 12px;
  font-size: 13px;
  cursor: pointer;
}

.new-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.welcome {
  text-align: center;
  color: #606266;
  font-size: 14px;
  line-height: 1.9;
  margin: 24px 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 16px 18px;
}

.bubble-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 12px;
}

.bubble-row.user {
  justify-content: flex-end;
}

.bubble-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  font-size: 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e4e7ed;
  color: #333;
  line-height: 1.6;
  font-size: 14px;
  word-break: break-word;
  white-space: pre-wrap;
}

.bubble-row.assistant .bubble {
  border-top-left-radius: 4px;
}

.bubble-row.user .bubble {
  background: linear-gradient(135deg, #409eff, #337ecc);
  border-color: #337ecc;
  color: #fff;
  border-top-right-radius: 4px;
}

.thinking {
  color: #909399;
  font-size: 12px;
  margin-left: 6px;
}

.steps-toggle {
  display: block;
  margin-top: 8px;
  border: 1px solid #409eff;
  background: #fff;
  color: #409eff;
  border-radius: 12px;
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
}

.steps-panel {
  margin-top: 8px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafbfc;
  padding: 8px;
}

.step {
  padding: 6px 4px;
  border-bottom: 1px dashed #e4e7ed;
}

.step:last-child {
  border-bottom: none;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.step-no {
  font-size: 11px;
  font-weight: 600;
  color: #409eff;
  flex-shrink: 0;
}

.step-tool {
  font-size: 12px;
  font-weight: 600;
  color: #333;
}

.step-status {
  font-size: 11px;
  color: #67c23a;
  border: 1px solid #67c23a;
  border-radius: 8px;
  padding: 0 6px;
  line-height: 16px;
  margin-left: auto;
}

.step-status.failed {
  color: #f56c6c;
  border-color: #f56c6c;
}

.step-thought {
  margin: 0 0 4px;
  font-size: 12px;
  color: #606266;
  white-space: pre-wrap;
}

.step-args {
  margin: 0 0 4px;
  font-size: 11px;
  color: #909399;
  white-space: pre-wrap;
}

.step-obs {
  margin: 0;
  font-size: 11px;
  color: #606266;
  background: #f2f3f5;
  border-radius: 6px;
  padding: 6px 8px;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}

.error {
  color: #f56c6c;
  font-size: 13px;
  text-align: center;
  margin: 8px 0;
}

.quick-row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 8px 12px;
  background: transparent;
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

.disclaimer {
  margin: 0;
  padding: 8px 16px calc(6px + env(safe-area-inset-bottom));
  font-size: 11px;
  color: #b0b3b8;
  text-align: center;
  background: #fff;
}
</style>
