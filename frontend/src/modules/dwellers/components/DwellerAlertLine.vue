<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useDwellerDetailContext } from './DwellerDetailContext'
import { getEffectiveMaxHealth, isMature } from '../models/dweller'

interface Alert {
  icon: string
  text: string
  tone: 'warning' | 'danger'
}

const ctx = useDwellerDetailContext()

const alerts = computed<Alert[]>(() => {
  const d = ctx.dweller.value
  if (!d || d.is_dead) return []

  const out: Alert[] = []
  const effectiveMax = getEffectiveMaxHealth(d.radiation, d.max_health)
  if (d.health < effectiveMax) {
    out.push({ icon: 'mdi:heart-pulse', text: `Injured — ${d.health}/${effectiveMax} HP`, tone: 'danger' })
  }
  if ((d.radiation ?? 0) > 0) {
    out.push({ icon: 'mdi:radiation', text: `Radiated — ${d.radiation}`, tone: 'warning' })
  }
  const happiness = d.happiness ?? 50
  if (happiness < 50) {
    out.push({ icon: 'mdi:emoticon-sad-outline', text: `Unhappy — ${happiness}%`, tone: 'warning' })
  }
  if (!d.room && d.status !== 'exploring' && d.status !== 'questing') {
    out.push({
      icon: 'mdi:account-question-outline',
      text: isMature(d) ? 'Unassigned — no room' : 'Unassigned — no apprenticeship',
      tone: 'warning',
    })
  }
  return out
})
</script>

<template>
  <div v-if="alerts.length" class="alert-line" role="status" aria-label="Dweller alerts">
    <span v-for="alert in alerts" :key="alert.text" class="alert-chip" :class="`alert-${alert.tone}`">
      <Icon :icon="alert.icon" class="alert-icon" />
      {{ alert.text }}
    </span>
  </div>
</template>

<style scoped>
.alert-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.alert-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.6rem;
  border: 1px solid currentColor;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.35);
  font-size: 0.75rem;
  white-space: nowrap;
}

.alert-warning {
  color: var(--color-warning);
}

.alert-danger {
  color: var(--color-danger);
}

.alert-icon {
  width: 0.9rem;
  height: 0.9rem;
  flex-shrink: 0;
}
</style>
