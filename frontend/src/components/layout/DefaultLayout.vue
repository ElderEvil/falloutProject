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
.flicker {
  animation: flicker 1.5s infinite alternate;
}

@keyframes flicker {
  0%,
  18%,
  22%,
  25%,
  53%,
  57%,
  100% {
    opacity: 1;
  }
  20%,
  24%,
  55% {
    opacity: 0.8;
  }
  21%,
  23% {
    opacity: 0.9;
  }
  26% {
    opacity: 0.65;
  }
  27% {
    opacity: 0.9;
  }
  54% {
    opacity: 0.95;
  }
  56% {
    opacity: 0.8;
  }
}
</style>
