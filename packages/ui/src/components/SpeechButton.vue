<script setup lang="ts">
import { computed } from 'vue'
import { useSpeech } from '../composables/useSpeech'

const props = defineProps<{
  id: string
  text: string
  disabled?: boolean
}>()

const speech = useSpeech()

const active = computed(() => speech.isActive(props.id))
const playing = computed(() => speech.isPlaying(props.id))
</script>

<template>
  <div class="speech-row">
    <button
      class="speech-btn"
      :class="{ active }"
      :disabled="disabled || !text.trim()"
      :aria-label="active && playing ? '暂停朗读' : active ? '继续朗读' : '朗读'"
      @click="speech.toggle(id, text)"
    >
      <template v-if="active && playing">
        ⏸
      </template>
      <template v-else>
        ▶
      </template>
    </button>
    <button
      v-if="active"
      class="speech-btn speech-stop"
      aria-label="停止朗读"
      @click="speech.stop"
    >
      ⏹
    </button>
  </div>
</template>

<style scoped>
.speech-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.speech-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: 1px solid #dcdfe6;
  border-radius: 50%;
  background: #fff;
  color: #909399;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
}

.speech-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.speech-btn.active {
  border-color: #409eff;
  color: #409eff;
}

.speech-stop {
  border-color: #f56c6c;
  color: #f56c6c;
}
</style>
