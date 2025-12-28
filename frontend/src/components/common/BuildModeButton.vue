<script setup lang="ts">
interface Props {
  buildModeActive: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'toggleBuildMode'): void
}>()
</script>

<template>
  <UButton
    @click="emit('toggleBuildMode')"
    :color="buildModeActive ? 'red' : 'primary'"
    variant="outline"
    size="lg"
    :icon="buildModeActive ? 'i-lucide-x' : 'i-lucide-wrench'"
    class="uppercase font-bold"
  >
    {{ buildModeActive ? 'CANCEL BUILDING' : 'BUILD MODE' }}
  </UButton>
</template>
