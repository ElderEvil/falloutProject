<script setup lang="ts">
import NavBar from '@/core/components/common/NavBar.vue'

defineProps<{
  isFlickering: boolean
}>()
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <NavBar />
    <main id="main-content" class="flex-grow" :class="{ flicker: isFlickering }" role="main">
      <slot></slot>
    </main>
  </div>
</template>

<style scoped>
/* Add styles as needed */
</style>
