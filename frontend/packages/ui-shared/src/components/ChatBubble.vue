<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  role: 'user' | 'assistant'
  text: string
  streaming?: boolean
}

const props = withDefaults(defineProps<Props>(), { streaming: false })

const isUser = computed(() => props.role === 'user')
</script>

<template>
  <div class="bubble-row" :class="{ 'is-user': isUser }">
    <div class="bubble" :class="isUser ? 'bubble-user' : 'bubble-assistant'">
      <span class="text">{{ text }}</span>
      <span v-if="streaming" class="cursor">▍</span>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  width: 100%;
  margin: 10px 0;
  justify-content: flex-start;
}
.bubble-row.is-user {
  justify-content: flex-end;
}
.bubble {
  max-width: var(--bubble-max-width, 75%);
  padding: 14px 18px;
  border-radius: var(--radius-md, 16px);
  font-size: var(--font-base, 18px);
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}
.bubble-user {
  background: var(--color-primary, #1e63d6);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.bubble-assistant {
  background: var(--color-surface, #fff);
  color: var(--color-text, #1a2433);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.cursor {
  display: inline-block;
  margin-left: 2px;
  animation: blink 1s steps(2, start) infinite;
  color: var(--color-primary, #1e63d6);
}
@keyframes blink {
  to {
    visibility: hidden;
  }
}
</style>
