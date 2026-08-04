<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ChatBubble, ActionCard, FeedbackButtons } from '@my-robot/ui-shared'
import { getToken } from '@my-robot/api-client'
import { useChat } from '../composables/useChat'

const chat = useChat()
const input = ref('')
const scrollRef = ref<HTMLDivElement | null>(null)

const quickReplies = ['科室查询', '查房提醒', '用药说明', '今天天气']

onMounted(() => {
  const token = getToken()
  if (token) chat.connect(token, 'hospital')
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
</script>

<template>
  <div class="chat-app">
    <header class="topbar">
      <div class="brand">
        <span class="dot" />
        <span>医院智能服务屏</span>
        <span class="scene-tag">hospital</span>
      </div>
      <div class="right">
        <span class="state" :class="{ on: chat.connected.value }">
          {{ chat.connected.value ? '已连接' : '连接中…' }}
        </span>
        <button class="logout" @click="logout">退出</button>
      </div>
    </header>

    <div v-if="chat.error.value" class="alert">
      ⚠ {{ chat.error.value }}
    </div>

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
          placeholder="输入您的需求，如「骨科在哪」「查房提醒」"
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
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px var(--layout-padding);
  background: var(--color-surface);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-large);
  font-weight: 600;
  color: var(--color-primary);
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-success);
}
.scene-tag {
  font-size: 0.7em;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(30, 99, 214, 0.1);
  color: var(--color-primary);
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.state {
  color: var(--color-text-muted);
  font-size: 0.9em;
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
  padding: 12px var(--layout-padding) 20px;
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
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--color-primary);
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  font-size: 0.95em;
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
