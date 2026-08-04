<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  modelValue?: 1 | -1 | null
  disabled?: boolean
}
const props = withDefaults(defineProps<Props>(), { modelValue: null, disabled: false })
const emit = defineEmits<{ (e: 'update:modelValue', v: 1 | -1): void }>()

const like = computed(() => props.modelValue === 1)
const dislike = computed(() => props.modelValue === -1)

function vote(v: 1 | -1) {
  if (props.disabled) return
  emit('update:modelValue', v)
}
</script>

<template>
  <div class="feedback">
    <span class="label">答案有用吗？</span>
    <button
      class="btn"
      :class="{ active: like }"
      :disabled="disabled"
      @click="vote(1)"
      aria-label="有用"
    >
      👍
    </button>
    <button
      class="btn"
      :class="{ active: dislike }"
      :disabled="disabled"
      @click="vote(-1)"
      aria-label="没用"
    >
      👎
    </button>
  </div>
</template>

<style scoped>
.feedback {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8em;
  color: var(--color-text-muted, #6b7785);
  margin-top: 6px;
}
.btn {
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: var(--color-surface, #fff);
  border-radius: 999px;
  width: 32px;
  height: 32px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.15s;
}
.btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.btn.active {
  background: var(--color-primary, #1e63d6);
  border-color: var(--color-primary, #1e63d6);
}
</style>
