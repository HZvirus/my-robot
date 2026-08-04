<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { applyTheme, homeTheme } from '@my-robot/ui-shared'
import { getToken } from '@my-robot/api-client'
import LoginView from './views/LoginView.vue'
import ChatView from './views/ChatView.vue'
import { ref } from 'vue'

const authed = ref(!!getToken())

onMounted(() => {
  applyTheme(homeTheme)
  window.addEventListener('robot:unauthorized', onUnauthorized)
})

function onUnauthorized() {
  authed.value = false
}

const view = computed(() => (authed.value ? ChatView : LoginView))

function onLoggedIn() {
  authed.value = true
}
</script>

<template>
  <component :is="view" @logged-in="onLoggedIn" />
</template>
