<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    fullName?: string
    health?: number | null
    maxHealth?: number | null
  }>(),
  {
    fullName: undefined,
    health: null,
    maxHealth: null,
  }
)

const healthPercent = computed(() => {
  const { health, maxHealth } = props
  if (health === null || maxHealth === null || maxHealth <= 0 || health >= maxHealth) return null
  return Math.min(100, Math.max(0, (health / maxHealth) * 100))
})
const healthTone = computed(() => {
  const percent = healthPercent.value ?? 100
  if (percent <= 25) return 'danger'
  if (percent <= 50) return 'warning'
  return 'success'
})
const title = computed(() => {
  const name = props.fullName ?? props.name
  return healthPercent.value === null
    ? name
    : `${name} · ${props.health}/${props.maxHealth} HP`
})
</script>

<template>
  <span class="dweller-name-badge" aria-hidden="true" :title="title">
    <span class="dweller-name-text">{{ name }}</span>
    <span v-if="healthPercent !== null" class="dweller-health">
      <span
        class="dweller-health-fill"
        :class="`is-${healthTone}`"
        :style="{ width: `${healthPercent}%` }"
      />
    </span>
  </span>
</template>

<style scoped>
.dweller-name-badge {
  display: inline-flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.1em;
  max-width: 100%;
  padding: 0.06em 0.36em;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 25%, transparent);
  border-radius: 0.3em;
  background: color-mix(in srgb, black 78%, transparent);
  color: var(--color-theme-primary);
  font-size: var(--dweller-name-size, 0.625rem);
  font-weight: 600;
  line-height: 1.2;
  text-align: center;
  text-shadow: 0 1px 3px black;
  pointer-events: none;
}

.dweller-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dweller-health {
  display: block;
  height: 0.18em;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, black 65%, transparent);
}

.dweller-health-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--color-success);
  transition: width 200ms ease;
}

.dweller-health-fill.is-warning {
  background: var(--color-warning);
}

.dweller-health-fill.is-danger {
  background: var(--color-danger);
}

@media (prefers-reduced-motion: reduce) {
  .dweller-health-fill {
    transition: none;
  }
}
</style>
