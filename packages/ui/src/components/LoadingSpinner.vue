<script setup lang="ts">
defineProps<{
  size?: number
}>()
</script>

<template>
  <div class="spinner" :style="{ width: `${size ?? 24}px`, height: `${size ?? 24}px` }" />
</template>
