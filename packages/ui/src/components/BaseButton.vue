<script setup lang="ts">
defineProps<{
  type?: 'primary' | 'default'
  disabled?: boolean
}>()
</script>

<template>
  <button class="base-button" :class="type" :disabled="disabled">
    <slot />
  </button>
</template>
