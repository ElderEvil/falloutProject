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

const group = computed<AgeGroup>(() => {
  const g = String(props.ageGroup ?? '').toLowerCase()
  return g === 'child' || g === 'teen' || g === 'adult' ? g : 'adult'
})

const meta = computed(() => {
  switch (group.value) {
    case 'child':
      return { color: '#38bdf8', icon: 'mdi:baby-face-outline', label: 'Child' }
    case 'teen':
      return { color: '#818cf8', icon: 'mdi:account-school', label: 'Teen' }
    case 'adult':
    default:
      return { color: '#4ade80', icon: 'mdi:account', label: 'Adult' }
  }
})
</script>

<template>
  <span
    class="dweller-age-badge"
    :class="[`size-${size}`]"
    :style="{ borderColor: meta.color, color: meta.color }"
    :title="meta.label"
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
  border: 1px solid;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.4);
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
