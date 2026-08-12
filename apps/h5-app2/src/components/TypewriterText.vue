<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  text: string
  active?: boolean
}>()

const shown = ref('')

let rafId: number | undefined
let lastTick = 0

const STEP_MS = 16

function stop() {
  if (rafId !== undefined) {
    cancelAnimationFrame(rafId)
    rafId = undefined
  }
}

function start() {
  if (rafId !== undefined) return
  lastTick = 0
  const tick = (time: number) => {
    if (time - lastTick >= STEP_MS) {
      lastTick = time
      const full = props.text
      if (shown.value.length >= full.length) {
        stop()
        return
      }
      const remaining = full.length - shown.value.length
      const chars = Math.max(1, Math.min(4, Math.ceil(remaining / 20)))
      shown.value = full.slice(0, shown.value.length + chars)
    }
    rafId = requestAnimationFrame(tick)
  }
  rafId = requestAnimationFrame(tick)
}

watch(
  () => props.text,
  (val) => {
    if (props.active) start()
    else {
      shown.value = val
      stop()
    }
  },
  { immediate: true }
)

watch(
  () => props.active,
  (val) => {
    if (val) start()
    else if (shown.value.length < props.text.length) start()
  }
)

onBeforeUnmount(stop)
</script>

<template>
  <span>
    {{ shown }}<span
      v-if="active && shown.length < text.length"
      class="tw-caret"
    >▌</span>
  </span>
</template>

<style scoped>
.tw-caret {
  animation: tw-blink 0.8s steps(1) infinite;
}
@keyframes tw-blink {
  50% {
    opacity: 0;
  }
}
</style>
