<script setup lang="ts">
import { computed } from 'vue'
import {
  VAULT_BOY_ANIMATIONS,
  type VaultBoyAnimation,
  type VaultBoyAnimationId,
} from '@/core/utils/vaultBoyAnimations'

const props = defineProps<{
  animation: VaultBoyAnimationId
  pose: number
  definition?: VaultBoyAnimation
}>()
const emit = defineEmits<{ ready: [] }>()
const animation = computed(() => props.definition ?? VAULT_BOY_ANIMATIONS[props.animation])
const frame = computed(() => animation.value.frames[props.pose] ?? animation.value.frames[0]!)
</script>

<template>
  <svg :viewBox="`0 0 ${animation.canvas.join(' ')}`" aria-hidden="true">
    <svg
      :x="(animation.canvas[0] - frame[2]) / 2"
      :y="animation.canvas[1] - frame[3]"
      :width="frame[2]"
      :height="frame[3]"
      :viewBox="frame.join(' ')"
      overflow="hidden"
    >
      <image
        :href="animation.sheet"
        :width="animation.sheetSize?.[0] ?? 2048"
        :height="animation.sheetSize?.[1] ?? 1024"
        @load="emit('ready')"
        @error="emit('ready')"
      />
    </svg>
  </svg>
</template>
