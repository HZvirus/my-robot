<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ChatBubble, ActionCard, FeedbackButtons } from '@my-robot/ui-shared'
import { getToken } from '@my-robot/api-client'
import { useChat } from '../composables/useChat'

const chat = useChat()
const input = ref('')
const scrollRef = ref<HTMLDivElement | null>(null)
const careMode = ref(false)

const quickReplies = ['今天天气', '放点音乐', '开灯', '关灯', '陪我说说话']

onMounted(() => {
  const token = getToken()
  if (token) chat.connect(token, 'home')
})

onUnmounted(() => chat.disconnect())

function onSend() {
  const text = input.value.trim()
  if (!text) return
  chat.send(text)
  input.value = ''
  scrollToBottom()
}

function quick(text: string) {
  input.value = text
  onSend()
}

function scrollToBottom() {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function logout() {
  chat.disconnect()
  chat.clearToken()
  location.reload()
}

function toggleCare() {
  careMode.value = !careMode.value
  document.documentElement.style.fontSize = careMode.value ? '22px' : ''
}
</script>

<template>
  <div class="chat-app" :class="{ 'care-mode': careMode }">
    <header class="topbar">
      <div class="brand">
        <span class="avatar">🤖</span>
        <span>家庭照护小助手</span>
      </div>
      <div class="right">
        <button class="care-btn" :class="{ on: careMode }" @click="toggleCare">
          关怀模式
        </button>
        <span class="state" :class="{ on: chat.connected.value }">
          {{ chat.connected.value ? '在线' : '连接中' }}
        </span>
        <button class="logout" @click="logout">退出</button>
      </div>
    </header>

    <div v-if="chat.error.value" class="alert">⚠ {{ chat.error.value }}</div>

    <main ref="scrollRef" class="messages">
      <template v-for="m in chat.messages.value" :key="m.id">
        <ChatBubble
          :role="m.role"
          :text="m.text"
          :streaming="m.role === 'assistant' && chat.streaming.active && m === chat.messages.value[chat.messages.value.length - 1]"
        />
        <ActionCard v-if="m.action" :action="m.action" />
        <FeedbackButtons
          v-if="m.role === 'assistant' && m.text && !chat.streaming.active"
          :model-value="m.feedback ?? null"
          @update:model-value="(v: 1 | -1) => chat.feedback(m, v)"
        />
      </template>
    </main>

    <footer class="composer">
      <div class="quick">
        <button v-for="q in quickReplies" :key="q" @click="quick(q)">{{ q }}</button>
      </div>
      <form class="input-row" @submit.prevent="onSend">
        <input
          v-model="input"
          type="text"
          placeholder="想说什么都行，爷爷～"
          autocomplete="off"
        />
        <button type="submit">发送</button>
      </form>
    </footer>
  </div>
</template>

<style scoped>
.chat-app {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
}
.care-mode {
  font-size: 1.1em;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px var(--layout-padding);
  background: var(--color-surface);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-large);
  font-weight: 600;
  color: var(--color-primary-dark);
}
.avatar {
  font-size: 28px;
}
.right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.care-btn {
  border: 1px solid var(--color-primary);
  background: transparent;
  color: var(--color-primary-dark);
  border-radius: 999px;
  padding: 6px 12px;
  cursor: pointer;
}
.care-btn.on {
  background: var(--color-primary);
  color: #fff;
}
.state {
  color: var(--color-text-muted);
  font-size: 0.85em;
}
.state.on {
  color: var(--color-success);
}
.logout {
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: transparent;
  border-radius: var(--radius-sm);
  padding: 6px 12px;
  cursor: pointer;
}
.alert {
  margin: var(--layout-padding) var(--layout-padding) 0;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: rgba(229, 72, 77, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(229, 72, 77, 0.3);
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--layout-padding);
  display: flex;
  flex-direction: column;
}
.composer {
  padding: 10px var(--layout-padding) 18px;
  background: var(--color-surface);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}
.quick {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.quick button {
  padding: 10px 16px;
  border-radius: 999px;
  border: 1px solid var(--color-primary);
  background: transparent;
  color: var(--color-primary-dark);
  cursor: pointer;
  font-size: 1em;
}
.input-row {
  display: flex;
  gap: 10px;
}
.input-row input {
  flex: 1;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(0, 0, 0, 0.12);
  font-size: var(--font-base);
}
.input-row button {
  padding: 0 28px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-base);
  cursor: pointer;
}
</style>
