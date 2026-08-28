<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

type AgeGroup = 'child' | 'teen' | 'adult'

const props = withDefaults(
  defineProps<{
    ageGroup?: AgeGroup | string | null
    showLabel?: boolean
    size?: 'sm' | 'md'
  }>(),
  { ageGroup: null, showLabel: false, size: 'md' }
)

const AGE_META: Record<AgeGroup, { color: string; icon: string; label: string }> = {
  child: { color: '#38bdf8', icon: 'mdi:baby-face-outline', label: 'Child' },
  teen: { color: '#818cf8', icon: 'mdi:account-school', label: 'Teen' },
  adult: { color: '#4ade80', icon: 'mdi:account', label: 'Adult' },
}

const group = computed<AgeGroup>(() => {
  const g = String(props.ageGroup ?? '').toLowerCase()
  return (g === 'child' || g === 'teen' || g === 'adult' ? g : 'adult') as AgeGroup
})

const meta = computed(() => AGE_META[group.value])
</script>

<template>
    <span
      class="dweller-age-badge"
      :class="[`size-${size}`]"
      :style="{ '--age-color': meta.color }"
      :title="meta.label"
      :aria-label="meta.label"
      role="img"
    >
      <Icon :icon="meta.icon" class="age-icon" />
      <span v-if="showLabel" class="age-label">{{ meta.label }}</span>
    </span>
</template>

<style scoped>
.dweller-age-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border: 1px solid var(--age-color);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.4);
  color: var(--age-color);
  white-space: nowrap;
}

.size-sm {
  padding: 0.15rem 0.4rem;
  font-size: 0.7rem;
}

.size-md {
  padding: 0.4rem 0.8rem;
  font-size: 0.8rem;
}

.age-icon {
  font-size: 0.9em;
}

.age-label {
  font-weight: 700;
  text-transform: capitalize;
}
</style>
