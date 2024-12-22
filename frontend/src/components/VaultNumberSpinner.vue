<script setup lang="ts">
import { ref, onMounted } from 'vue';

const props = defineProps<{
  finalNumber: number;
}>();

const currentNumber = ref(0);
const isSpinning = ref(true);

onMounted(() => {
  let count = 0;
  const interval = setInterval(() => {
    currentNumber.value = Math.floor(Math.random() * 999) + 1;
    count++;

    if (count > 20) {
      clearInterval(interval);
      currentNumber.value = props.finalNumber;
      isSpinning.value = false;
    }
  }, 100);
});
</script>

<template>
  <div class="number-display" :class="{ spinning: isSpinning }">
    {{ currentNumber.toString().padStart(3, '0') }}
  </div>
</template>

<style scoped>
.number-display {
  font-family: 'Courier New', monospace;
  font-size: 2em;
  font-weight: bold;
  letter-spacing: 2px;
}

.spinning {
  text-shadow: 0 0 15px #00ff00;
}
</style>
