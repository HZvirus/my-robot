<script setup lang="ts">
import { ref } from 'vue'
import { useSpeech } from '@my-robot/ui'
import { getProfile, updateProfile } from '@/api/profile'

const speech = useSpeech()
const nickname = ref('')
const loading = ref(false)

async function load() {
  const res = await getProfile()
  nickname.value = res.data.nickname
}

async function save() {
  loading.value = true
  try {
    await updateProfile({ nickname: nickname.value })
  } finally {
    loading.value = false
  }
}

void load()
</script>

<template>
  <div class="settings">
    <h2>设置</h2>

    <section class="card">
      <h3>基本信息</h3>
      <div class="row">
        <span>昵称</span>
        <input
          v-model="nickname"
          placeholder="昵称"
        >
      </div>
      <button
        class="save-btn"
        :disabled="loading"
        @click="save"
      >
        保存
      </button>
    </section>

    <section class="card">
      <h3>朗读设置</h3>
      <label class="row">
        <span>自动朗读回复</span>
        <input
          v-model="speech.settings.autoRead"
          type="checkbox"
        >
      </label>
      <label class="row">
        <span>音色</span>
        <select v-model="speech.settings.voice">
          <option
            v-for="v in speech.voices"
            :key="v.value"
            :value="v.value"
          >
            {{ v.label }}
          </option>
        </select>
      </label>
      <label class="row">
        <span>语速 {{ speech.settings.speed }}</span>
        <input
          v-model.number="speech.settings.speed"
          type="range"
          min="0"
          max="100"
        >
      </label>
      <label class="row">
        <span>音量 {{ speech.settings.volume }}</span>
        <input
          v-model.number="speech.settings.volume"
          type="range"
          min="0"
          max="100"
        >
      </label>
      <label class="row">
        <span>音高 {{ speech.settings.pitch }}</span>
        <input
          v-model.number="speech.settings.pitch"
          type="range"
          min="0"
          max="100"
        >
      </label>
    </section>
  </div>
</template>

<style scoped>
.settings {
  max-width: 480px;
  margin: 0 auto;
  padding: 16px;
}

h2 {
  margin: 0 0 16px;
  font-size: 18px;
}

.card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

h3 {
  margin: 0 0 12px;
  font-size: 15px;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  font-size: 14px;
}

.row input[type='text'],
.row input[type='number'],
.row select {
  flex: 1;
  max-width: 200px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 14px;
}

.row input[type='range'] {
  flex: 1;
}

.save-btn {
  margin-top: 8px;
  border: none;
  border-radius: 8px;
  background: #67c23a;
  color: #fff;
  padding: 8px 20px;
  font-size: 14px;
  cursor: pointer;
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
