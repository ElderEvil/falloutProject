<script setup lang="ts">
import type { VisualAttributes } from '@/types/dweller.types'

const props = defineProps<{
  visualAttributes: VisualAttributes
  gender?: 'male' | 'female'
  rarity?: string
}>()

const formatKey = (key: string) => key.replace(/_/g, ' ').toUpperCase()
</script>

<template>
  <div class="attributes-grid">
    <div v-if="gender" class="attribute-row">
      <span class="attribute-label">GENDER</span>
      <span class="attribute-value">{{ gender.toUpperCase() }}</span>
    </div>
    <div v-if="rarity" class="attribute-row">
      <span class="attribute-label">RARITY</span>
      <span class="attribute-value">{{ rarity.toUpperCase() }}</span>
    </div>
    <div v-for="[key, value] in Object.entries(visualAttributes)" :key="key" class="attribute-row">
      <span class="attribute-label">{{ formatKey(key) }}</span>
      <span class="attribute-value">{{ value.toString().toUpperCase() }}</span>
    </div>
  </div>
</template>

<style scoped>
.attributes-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.attribute-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.attribute-label {
  font-size: 0.8em;
  opacity: 0.8;
}

.attribute-value {
  font-size: 1em;
  font-weight: bold;
}
</style>
