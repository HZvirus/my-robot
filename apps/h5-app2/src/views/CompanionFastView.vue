<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BaseButton, LoadingSpinner } from '@my-robot/ui'
import { useSmartTts } from '@/composables/useSmartTts'
import TypewriterText from '@/components/TypewriterText.vue'
import { useCompanionStore } from '@/stores/companion'

const route = useRoute()
const router = useRouter()
const store = useCompanionStore()
const speech = useSmartTts()

const input = ref('')
const listEl = ref<HTMLElement | null>(null)

const id = typeof route.query.id === 'string' ? route.query.id : null
if (id) {
  void store.loadHistory(id)
}

const activeAssistantId = computed(() => {
  if (!store.streaming) return null
  for (let i = store.messages.length - 1; i >= 0; i--) {
    if (store.messages[i].role === 'assistant') return store.messages[i].id
  }
  return null
})

const voiceStateText = computed(() => {
  if (speech.state.value === 'playing') return '语音朗读中'
  if (speech.state.value === 'paused') return '已暂停朗读'
  return '语音就绪 · 直连'
})

const quickPrompts = [
  '最近工作压力很大，陪我聊聊好吗',
  '晚上总睡不好，有什么放松的方法',
  '帮我推荐一份一日三餐的健康搭配',
  '今天情绪很低落，想听你开导我'
]

function pickVoice(value: string) {
  speech.settings.voice = value
  if (speech.state.value !== 'idle') {
    const last = store.messages[store.messages.length - 1]
    if (last && last.role === 'assistant' && last.content) {
      speech.toggle(last.id, last.content)
    }
  }
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

// 离开页面时停止播报（传输层由路由 meta 驱动，无需手动恢复）
onBeforeUnmount(() => {
  speech.stop()
})
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
        <span class="avatar">安</span>
        <div class="title-text">
          <span class="chat-title">小安 · 健康陪伴快速版</span>
          <span class="chat-subtitle">讯飞超拟人 · WebSocket 直连</span>
        </div>
      </div>
      <div class="header-actions">
        <span
          class="voice-pill"
          :class="speech.state.value"
        >
          {{ voiceStateText }}
        </span>
        <button
          class="new-btn"
          :disabled="store.streaming"
          @click="newChat"
        >
          新对话
        </button>
      </div>
    </header>

    <div class="voice-panel">
      <div class="voice-row">
        <span class="voice-label">超拟人音色</span>
        <div class="voice-chips">
          <button
            v-for="v in speech.voices"
            :key="v.value"
            class="voice-chip"
            :class="{ active: speech.settings.voice === v.value }"
            :title="v.label"
            @click="pickVoice(v.value)"
          >
            {{ v.label.split('（')[0] }}
          </button>
        </div>
      </div>
      <label class="auto-read">
        <span>自动朗读回复</span>
        <input
          v-model="speech.settings.autoRead"
          type="checkbox"
        >
      </label>
    </div>

    <div
      ref="listEl"
      class="msg-list"
    >
      <p
        v-if="store.messages.length === 0"
        class="welcome"
      >
        你好呀，我是小安。快速版的我通过 WebSocket 直连讯飞超拟人语音，
        回复更快更自然——你的每句话我都会认真听，也会温柔地读给你听。
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
        >安</span>
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
            v-if="m.role === 'assistant' && speech.isPlaying(m.id)"
            class="speaking"
          >
            ● 正在朗读
          </span>
          <span
            v-if="m.interrupted && m.role === 'assistant'"
            class="interrupted"
          >
            （已中断）
          </span>
          <button
            v-if="m.role === 'assistant' && m.content"
            class="replay-btn"
            :class="{ active: speech.isActive(m.id) }"
            @click="speech.toggle(m.id, m.content)"
          >
            {{ speech.isActive(m.id) ? (speech.isPlaying(m.id) ? '停止' : '继续') : '重播' }}
          </button>
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
        placeholder="和小安快速版聊聊…"
        @keyup.enter="send"
      >
      <BaseButton
        type="primary"
        :disabled="!input.trim() || store.streaming"
        @click="send"
      >
        {{ store.streaming ? '陪伴中' : '发送' }}
      </BaseButton>
    </footer>

    <p class="disclaimer">
      小安快速版是 AI 健康陪伴助手，不提供医疗诊断。如有紧急症状请立即就医或拨打 120。
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
  background: linear-gradient(135deg, #67c23a, #3f9e4d);
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

.voice-pill {
  font-size: 11px;
  color: #3f9e4d;
  background: #eaf6ef;
  border-radius: 12px;
  padding: 3px 8px;
  white-space: nowrap;
}

.voice-pill.playing {
  color: #fff;
  background: #67c23a;
}

.voice-pill.paused {
  color: #b88230;
  background: #fdf3e0;
}

.new-btn {
  border: 1px solid #67c23a;
  color: #67c23a;
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

.voice-panel {
  background: #fff;
  border-bottom: 1px solid #eee;
  padding: 8px 12px;
}

.voice-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.voice-label {
  font-size: 12px;
  color: #606266;
  flex-shrink: 0;
}

.voice-chips {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.voice-chip {
  flex-shrink: 0;
  border: 1px solid #dcdfe6;
  color: #606266;
  background: #fff;
  border-radius: 14px;
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
}

.voice-chip.active {
  border-color: #67c23a;
  color: #3f9e4d;
  background: #eaf6ef;
  font-weight: 600;
}

.auto-read {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
  cursor: pointer;
}

.auto-read input {
  accent-color: #67c23a;
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
  background: linear-gradient(135deg, #67c23a, #3f9e4d);
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
  background: linear-gradient(135deg, #67c23a, #3f9e4d);
  border-color: #3f9e4d;
  color: #fff;
  border-top-right-radius: 4px;
}

.speaking {
  display: inline-block;
  color: #67c23a;
  font-size: 12px;
  margin-left: 6px;
  animation: pulse 1.2s ease-in-out infinite;
}

.interrupted {
  color: #c0c4cc;
  font-size: 12px;
  margin-left: 6px;
}

.replay-btn {
  display: inline-flex;
  align-items: center;
  margin-top: 6px;
  border: 1px solid #67c23a;
  background: #fff;
  color: #3f9e4d;
  border-radius: 12px;
  padding: 2px 10px;
  font-size: 12px;
  cursor: pointer;
}

.replay-btn.active {
  background: #67c23a;
  color: #fff;
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
  border: 1px solid #67c23a;
  color: #3f9e4d;
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
  border-color: #67c23a;
}

.disclaimer {
  margin: 0;
  padding: 8px 16px calc(6px + env(safe-area-inset-bottom));
  font-size: 11px;
  color: #b0b3b8;
  text-align: center;
  background: #fff;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.4;
  }
}
</style>
