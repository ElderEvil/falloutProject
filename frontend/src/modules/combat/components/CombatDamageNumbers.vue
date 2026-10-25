<script setup lang="ts">
defineProps<{
  numbers: Array<{ id: number; amount: number }>
}>()
</script>

<template>
  <div class="pointer-events-none absolute inset-0 z-2 overflow-hidden" aria-hidden="true">
    <span
      v-for="number in numbers"
      :key="number.id"
      class="damage-number absolute top-2.5 left-1/2 font-bold text-danger"
      >-{{ number.amount }}</span
    >
  </div>
</template>

<style scoped>
.damage-number {
  animation: damage-float 0.9s ease-out forwards;
}

@keyframes damage-float {
  from {
    opacity: 1;
    transform: translate(-50%, 0);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -32px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .damage-number {
    animation: none;
    transform: translateX(-50%);
  }
}
</style>
