<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="home">
    <h1>H5 App 1</h1>
    <button @click="router.push('/triage')">
      智能导诊
    </button>
  </div>
</template>
