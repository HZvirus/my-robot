<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BaseButton, LoadingSpinner, useSpeech } from '@my-robot/ui'
import TypewriterText from '@/components/TypewriterText.vue'
import { useCompanionStore } from '@/stores/companion'

const route = useRoute()
const router = useRouter()
const store = useCompanionStore()
const speech = useSpeech()

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

const quickPrompts = [
  '最近压力很大，想找人聊聊',
  '晚上总睡不好怎么办',
  '可以给我一些健康饮食的建议吗',
  '今天心情不太好'
]

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
          <span class="chat-title">小安 · 健康陪伴</span>
          <span class="chat-subtitle">随时陪你说说话</span>
        </div>
      </div>
      <button
        class="new-btn"
        :disabled="store.streaming"
        @click="newChat"
      >
        新对话
      </button>
    </header>

    <div
      ref="listEl"
      class="msg-list"
    >
      <p
        v-if="store.messages.length === 0"
        class="welcome"
      >
        你好呀，我是小安。工作累了、心里烦了、想聊聊身体和心情，
        都可以随时跟我说，我一直在这里陪着你。
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
        placeholder="和小安聊聊…"
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
      小安是 AI 健康陪伴助手，不提供医疗诊断。如有紧急症状请立即就医或拨打 120。
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
}

.title-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.chat-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.chat-subtitle {
  font-size: 11px;
  color: #909399;
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
</style>
