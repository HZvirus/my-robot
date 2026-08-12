<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BaseButton, LoadingSpinner, SpeechButton, TypewriterText } from '@my-robot/ui'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const store = useChatStore()

const input = ref('')
const listEl = ref<HTMLElement | null>(null)

const activeAssistantId = computed(() => {
  if (!store.streaming) return null
  for (let i = store.messages.length - 1; i >= 0; i--) {
    if (store.messages[i].role === 'assistant') return store.messages[i].id
  }
  return null
})

function send() {
  const text = input.value.trim()
  if (!text || store.streaming) return
  input.value = ''
  store.send(text)
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
      <span class="chat-title">智能助手</span>
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
        您好，我是智能助手。有什么可以帮您？
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
          <SpeechButton
            v-if="m.role === 'assistant' && m.content"
            :id="m.id"
            :text="m.content"
            :disabled="store.streaming"
          />
        </div>
      </div>

      <p
        v-if="store.error"
        class="error"
      >
        {{ store.error }}
      </p>
    </div>

    <footer class="input-bar">
      <input
        v-model="input"
        class="input"
        :disabled="store.streaming"
        placeholder="输入消息…"
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
.chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 720px;
  margin: 0 auto;
  background: #f5f7fa;
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

.chat-title {
  font-size: 16px;
  font-weight: 600;
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
  color: #999;
  font-size: 14px;
  line-height: 1.8;
  margin: 24px 16px;
}

.bubble-row {
  display: flex;
  margin-bottom: 12px;
}

.bubble-row.user {
  justify-content: flex-end;
}

.bubble-row.assistant {
  justify-content: flex-start;
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
