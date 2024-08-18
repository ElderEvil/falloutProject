<script setup lang="ts">
import NavBar from '@/components/common/NavBar.vue'

defineProps<{
  isFlickering: boolean
}>()
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <NavBar />
    <main class="flex-grow" :class="{ flicker: isFlickering }">
      <slot></slot>
    </main>
  </div>
</template>

<style scoped>
/* Add styles as needed */
</style>
