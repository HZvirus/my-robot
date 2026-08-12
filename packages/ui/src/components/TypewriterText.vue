<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  text: string
  active?: boolean
}>()

const shown = ref('')
let timer: number | undefined

function stop() {
  if (timer !== undefined) {
    window.clearTimeout(timer)
    timer = undefined
  }
}

function start() {
  if (timer !== undefined) return
  const step = () => {
    const full = props.text
    if (shown.value.length >= full.length) {
      stop()
      return
    }
    const remaining = full.length - shown.value.length
    const chars = Math.max(1, Math.ceil(remaining / 6))
    shown.value = full.slice(0, shown.value.length + chars)
    timer = window.setTimeout(step, 16)
  }
  step()
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
    else {
      shown.value = props.text
      stop()
    }
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
