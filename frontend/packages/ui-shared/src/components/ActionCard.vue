<script setup lang="ts">
import { computed } from 'vue'

interface ActionPayload {
  id: string
  type: string
  params: Record<string, any>
  status?: string
}

const props = defineProps<{ action: ActionPayload }>()

const title = computed(() => {
  const map: Record<string, string> = {
    weather_broadcast: '天气播报',
    dept_round: '查房安排',
    home_light: '灯光控制',
    play_media: '媒体播放',
    speak: '语音播报',
  }
  return map[props.action.type] ?? props.action.type
})

const desc = computed(() => {
  const p = props.action.params || {}
  if (props.action.type === 'weather_broadcast') return p.text ?? `${p.city ?? ''} 天气播报`
  if (props.action.type === 'home_light') return `${p.device ?? '设备'} ${p.action ?? ''}`
  if (props.action.type === 'play_media') return `${p.media ?? '媒体'} · ${p.duration_sec ?? 0}秒`
  if (props.action.type === 'dept_round') return p.target_dept ?? '排程中'
  return JSON.stringify(p)
})
</script>

<template>
  <div class="action-card">
    <div class="head">
      <span class="icon">▶</span>
      <span class="title">{{ title }}</span>
      <span class="status" :class="action.status">{{ action.status ?? 'queued' }}</span>
    </div>
    <div class="desc">{{ desc }}</div>
  </div>
</template>

<style scoped>
.action-card {
  margin: 8px 0;
  border-radius: var(--radius-md, 16px);
  background: linear-gradient(135deg, rgba(14, 159, 110, 0.08), rgba(14, 159, 110, 0.02));
  border: 1px solid rgba(14, 159, 110, 0.25);
  padding: 14px 16px;
  font-size: var(--font-base, 18px);
}
.head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.icon {
  color: var(--color-action, #0e9f6e);
}
.title {
  font-weight: 600;
  color: var(--color-text, #1a2433);
}
.status {
  margin-left: auto;
  font-size: 0.8em;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(14, 159, 110, 0.15);
  color: var(--color-action, #0e9f6e);
}
.desc {
  margin-top: 6px;
  color: var(--color-text-muted, #6b7785);
}
</style>
