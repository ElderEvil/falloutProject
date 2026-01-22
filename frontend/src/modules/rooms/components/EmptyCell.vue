<script setup lang="ts">
import { computed } from 'vue'
import { useHoverPreview } from '@/composables/useHoverPreview'

const props = defineProps({
  x: {
    type: Number,
    required: true
  },
  y: {
    type: Number,
    required: true
  }
})

const { handleHover, clearHover, isValidPlacement, previewCells } = useHoverPreview()

const isHoverPreview = computed(() => {
  return previewCells.value.some((cell) => cell.x === props.x && cell.y === props.y)
})
</script>

<template>
  <div
    class="room empty"
    :class="{
      'hover-preview': isHoverPreview,
      'valid-placement': isValidPlacement && isHoverPreview,
      'invalid-placement': isHoverPreview && !isValidPlacement
    }"
    @mouseenter="handleHover(props.x, props.y)"
    @mouseleave="clearHover"
  ></div>
</template>

<style scoped>
.empty {
  border: 1px dashed #555;
  background-color: rgba(0, 0, 0, 0.3);
  aspect-ratio: 2 / 1;
}

.hover-preview {
  background-color: rgba(0, 255, 0, 0.3);
  z-index: 1;
}

.valid-placement .hover-preview {
  background-color: transparent;
  background-image: linear-gradient(
    45deg,
    rgba(0, 255, 0, 0.5) 25%,
    transparent 25%,
    transparent 50%,
    rgba(0, 255, 0, 0.5) 50%,
    rgba(0, 255, 0, 0.5) 75%,
    transparent 75%,
    transparent
  );
  background-size: 20px 20px;
  border: 2px solid #00ff00;
}

.invalid-placement .hover-preview {
  background-color: transparent;
  background-image: linear-gradient(
    45deg,
    rgba(255, 0, 0, 0.5) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255, 0, 0, 0.5) 50%,
    rgba(255, 0, 0, 0.5) 75%,
    transparent 75%,
    transparent
  );
  background-size: 20px 20px;
  border: 2px solid #ff0000;
}
</style>
