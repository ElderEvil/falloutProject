<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import { useGameBalance } from '@/core/composables/useGameBalance'
import type { RoomRushQuote } from '../models/room'
import { formatRushPayout, rushConsequenceTags } from '../utils/roomRush'

interface Props {
  quote: RoomRushQuote | null
  loading: boolean
  rushing: boolean
  error: string | null
  blockedMessage: string
}

const props = defineProps<Props>()
const emit = defineEmits<{ rush: [] }>()

const { rushHappinessDelta } = useGameBalance()
const showBreakdown = ref(false)

const riskLabel = computed(() => (props.quote ? Math.round(props.quote.fail_chance) : 0))
const successLabel = computed(() => (props.quote ? Math.round(props.quote.success_chance) : 0))
const avgAbilityLabel = computed(() => props.quote?.avg_ability.toFixed(1) ?? '0.0')
const avgLuckLabel = computed(() => props.quote?.avg_luck.toFixed(1) ?? '0.0')
const consequenceTags = computed(() => rushConsequenceTags(props.quote?.eligible_incidents ?? []))
const payoutPreview = computed(() => (props.quote ? formatRushPayout(props.quote.payout) : ''))
const happinessPenalty = computed(() => rushHappinessDelta.value)
const stackPenalty = computed(() => (props.quote ? props.quote.stacks * 10 : 0))
const breakdownRows = computed(() => {
  const quote = props.quote
  if (!quote) return []
  const rows = [
    { label: 'Success', value: `${successLabel.value}%` },
    { label: 'SPECIAL (gear)', value: avgAbilityLabel.value },
    { label: 'Luck (gear)', value: avgLuckLabel.value },
    { label: 'Workers', value: String(quote.worker_count) },
  ]
  if (stackPenalty.value > 0) rows.push({ label: 'Rush penalty', value: `+${stackPenalty.value}%` })
  return rows
})
const rushAriaLabel = computed(() => {
  if (!props.quote?.can_rush) return props.blockedMessage || 'Rush unavailable'
  return `Rush the room (${riskLabel.value}% incident chance)`
})
</script>

<template>
  <div class="section">
    <h3 class="section-title">
      <Icon icon="mdi:lightning-bolt" class="h-5 w-5" />
      Rush Production
    </h3>

    <div v-if="loading" class="rush-loading">Checking the odds...</div>
    <div v-else-if="error" class="rush-error">{{ error }}</div>
    <div v-else-if="quote" class="rush-card">
      <div class="rush-risk">
        <span class="rush-risk__label">Incident chance</span>
        <div class="rush-risk__main">
          <TooltipProvider :delay-duration="150">
            <Tooltip>
              <TooltipTrigger as-child>
                <span
                  class="rush-risk__value"
                  tabindex="0"
                  :aria-label="`${riskLabel}% incident chance. Focus for contributing factors.`"
                >
                  {{ riskLabel }}%
                </span>
              </TooltipTrigger>
              <TooltipContent class="max-w-64">
                <dl class="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
                  <div v-for="row in breakdownRows" :key="row.label" class="contents">
                    <dt class="text-theme-primary/60">{{ row.label }}</dt>
                    <dd class="text-right">{{ row.value }}</dd>
                  </div>
                </dl>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <span v-if="stackPenalty > 0" class="rush-risk__penalty">
            Rush penalty +{{ stackPenalty }}%
          </span>
        </div>
      </div>

      <Button
        variant="ghost"
        size="xs"
        class="rush-why"
        :aria-expanded="showBreakdown"
        @click="showBreakdown = !showBreakdown"
      >
        Why these odds?
      </Button>

      <dl v-if="showBreakdown" id="rush-breakdown" class="rush-breakdown">
        <div v-for="row in breakdownRows" :key="row.label" class="contents">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.value }}</dd>
        </div>
      </dl>

      <div class="rush-consequences">
        <span class="rush-consequences__label">Possible incidents</span>
        <span v-for="tag in consequenceTags" :key="tag" class="rush-consequence">{{ tag }}</span>
        <span v-if="happinessPenalty !== null" class="rush-consequence rush-consequence--happiness">
          −{{ happinessPenalty }} Happiness
        </span>
      </div>

      <p class="rush-payout">On success: {{ payoutPreview }}</p>

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
        {{ rushing ? 'Rushing...' : 'Rush' }}
      </Button>
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
  gap: 0.55rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  background: var(--color-surface-sunken);
}

.rush-risk {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.rush-risk__label {
  color: var(--color-gray-400);
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.rush-risk__main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.rush-risk__value {
  border-bottom: 1px dotted var(--color-warning);
  color: var(--color-warning);
  font-size: 2rem;
  font-weight: 800;
  line-height: 1;
  cursor: help;
}

.rush-risk__value:hover,
.rush-risk__value:focus-visible {
  text-shadow: 0 0 12px color-mix(in srgb, var(--color-warning) 65%, transparent);
  outline: none;
}

.rush-risk__value:focus-visible {
  outline: 1px solid var(--color-warning);
  outline-offset: 3px;
}

.rush-risk__penalty {
  padding: 0.1rem 0.35rem;
  border: 1px solid var(--color-warning);
  border-radius: 3px;
  color: var(--color-warning);
  font-size: 0.6875rem;
  letter-spacing: 0.05em;
}

.rush-why {
  align-self: flex-start;
  color: var(--color-theme-primary);
}

.rush-breakdown {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.15rem 0.75rem;
  margin: 0;
  padding: 0.45rem 0.55rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  font-size: 0.75rem;
}

.rush-breakdown dt {
  color: var(--color-gray-400);
}

.rush-breakdown dd {
  margin: 0;
  color: var(--color-theme-primary);
  text-align: right;
}

.rush-consequences {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.rush-consequences__label {
  color: var(--color-gray-400);
  font-size: 0.6875rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.rush-consequence {
  padding: 0.1rem 0.35rem;
  border: 1px solid var(--color-warning);
  border-radius: 3px;
  color: var(--color-warning);
  font-size: 0.6875rem;
  letter-spacing: 0.05em;
}

.rush-consequence--happiness {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.rush-payout {
  margin: 0;
  color: var(--color-theme-primary);
  font-size: 0.8125rem;
}

.rush-loading {
  color: var(--color-gray-400);
  font-size: 0.75rem;
}

.rush-blocked,
.rush-error {
  margin: 0;
  color: var(--color-warning);
  font-size: 0.75rem;
}

.rush-button {
  align-self: flex-start;
}
</style>
