<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import type { RoomRushQuote, RoomRushResourceGain, RoomRushResult } from '../models/room'

interface Props {
  quote: RoomRushQuote | null
  result: RoomRushResult | null
  loading: boolean
  rushing: boolean
  error: string | null
  blockedMessage: string
}

const props = defineProps<Props>()
const emit = defineEmits<{ rush: [] }>()

type PayoutKey = keyof RoomRushResourceGain

const PAYOUT_LABELS: Record<PayoutKey, string> = {
  power: 'Power',
  food: 'Food',
  water: 'Water',
  stimpack: 'Stimpacks',
  radaway: 'RadAway',
}

const payoutRows = computed(() =>
  props.quote
    ? (Object.entries(props.quote.payout) as [PayoutKey, number][])
        .filter(([, amount]) => amount > 0)
        .map(([key, amount]) => ({ label: PAYOUT_LABELS[key], amount }))
    : []
)

const resultRows = computed(() =>
  props.result
    ? (Object.entries(props.result.payout) as [PayoutKey, number][])
        .filter(([, amount]) => amount > 0)
        .map(([key, amount]) => ({ label: PAYOUT_LABELS[key], amount }))
    : []
)

const riskLabel = computed(() => (props.quote ? Math.round(props.quote.fail_chance) : 0))
const successLabel = computed(() => (props.quote ? Math.round(props.quote.success_chance) : 0))
const capsChanceLabel = computed(() => (props.quote ? Math.round(props.quote.caps_chance) : 0))
const incidentLabel = computed(() =>
  props.result?.incident_type ? props.result.incident_type.replaceAll('_', ' ') : null
)

const rushAriaLabel = computed(() => {
  if (!props.quote?.can_rush) return props.blockedMessage || 'Rush unavailable'
  return `Rush production (${riskLabel.value}% risk)`
})
</script>

<template>
  <div class="section">
    <h3 class="section-title">
      <Icon icon="mdi:lightning-bolt" class="h-5 w-5" />
      Rush Production
    </h3>

    <div v-if="loading" class="rush-loading">Calculating risk...</div>
    <div v-else-if="error" class="rush-error">{{ error }}</div>
    <div v-else-if="quote" class="rush-card">
      <div class="rush-stats">
        <div class="rush-stat">
          <span>Risk</span>
          <strong>{{ riskLabel }}%</strong>
        </div>
        <div class="rush-stat">
          <span>Success</span>
          <strong>{{ successLabel }}%</strong>
        </div>
        <div class="rush-stat">
          <span>Recent rushes</span>
          <strong>{{ quote.stacks }}/{{ quote.max_stacks }}</strong>
        </div>
        <div class="rush-stat">
          <span>Caps chance</span>
          <strong>{{ capsChanceLabel }}%</strong>
        </div>
      </div>

      <div v-if="payoutRows.length" class="rush-payout">
        <span class="rush-payout__label">Payout</span>
        <span v-for="row in payoutRows" :key="row.label" class="rush-payout__item">
          +{{ row.amount }} {{ row.label }}
        </span>
      </div>
      <p v-else class="rush-note">
        Resource payout is zero at current capacity. Caps can still be earned.
      </p>

      <p v-if="!quote.can_rush" class="rush-blocked">{{ blockedMessage }}</p>

      <Button
        variant="default"
        size="sm"
        class="rush-button"
        :disabled="!quote.can_rush || rushing"
        :aria-label="rushAriaLabel"
        @click="emit('rush')"
      >
        <Icon icon="mdi:lightning-bolt" />
        {{ rushing ? 'Rushing...' : 'Rush Production' }}
      </Button>

      <p class="rush-warning">
        Failure can start a fire or infestation and hurt assigned dwellers.
      </p>

      <div
        v-if="result"
        class="rush-result"
        :class="result.outcome === 'success' ? 'rush-result--success' : 'rush-result--failure'"
      >
        <div class="rush-result__stamp rush-stamp">
          {{ result.outcome === 'success' ? 'RUSH OK' : 'RUSH FAIL' }}
        </div>
        <p>{{ result.message }}</p>
        <p v-if="resultRows.length">
          Produced: {{ resultRows.map((row) => `+${row.amount} ${row.label}`).join(', ') }}
        </p>
        <p v-if="result.caps > 0">Caps bonus: +{{ result.caps }}</p>
        <p v-if="result.outcome === 'failure' && incidentLabel">Incident: {{ incidentLabel }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  color: var(--color-theme-primary);
  font-size: 0.9375rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.section-title :deep(svg) {
  width: 1rem;
  height: 1rem;
}

.rush-card {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.65rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  background: var(--color-surface-sunken);
}

.rush-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.4rem;
}

.rush-stat {
  padding: 0.4rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  text-align: center;
}

.rush-stat span {
  display: block;
  color: var(--color-gray-400);
  font-size: 0.6875rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.rush-stat strong {
  display: block;
  margin-top: 0.15rem;
  color: var(--color-theme-primary);
  font-size: 1rem;
}

.rush-payout {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
}

.rush-payout__label {
  color: var(--color-gray-400);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.rush-payout__item {
  padding: 0.1rem 0.35rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 3px;
  color: var(--color-success);
}

.rush-loading,
.rush-note {
  color: var(--color-gray-400);
  font-size: 0.75rem;
}

.rush-blocked,
.rush-error {
  color: var(--color-warning);
  font-size: 0.75rem;
}

.rush-warning {
  color: var(--color-gray-400);
  font-size: 0.6875rem;
}

.rush-button {
  align-self: flex-start;
}

.rush-result {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.5rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  font-size: 0.75rem;
}

.rush-result p {
  margin: 0;
}

.rush-result--success {
  border-color: var(--color-success);
}

.rush-result--failure {
  border-color: var(--color-danger);
}

.rush-result__stamp {
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.rush-result--success .rush-result__stamp {
  color: var(--color-success);
}

.rush-result--failure .rush-result__stamp {
  color: var(--color-danger);
}

@media (max-width: 640px) {
  .rush-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
