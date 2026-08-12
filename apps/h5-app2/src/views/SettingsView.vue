<script setup lang="ts">
import { ref } from 'vue'
import { getProfile, updateProfile } from '@/api/profile'

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
    <input
      v-model="nickname"
      placeholder="昵称"
    >
    <button
      :disabled="loading"
      @click="save"
    >
      保存
    </button>
  </div>
</template>
