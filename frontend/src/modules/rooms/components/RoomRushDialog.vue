<script setup lang="ts">
import { computed } from 'vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import { useGameBalance } from '@/core/composables/useGameBalance'
import type { RoomRushQuote } from '../models/room'
import { formatRushPayout, rushConsequenceTags } from '../utils/roomRush'

interface Props {
  open: boolean
  roomName: string
  quote: RoomRushQuote | null
  loading: boolean
  rushing: boolean
  error: string | null
  blockedMessage: string
}

const props = defineProps<Props>()
const emit = defineEmits<{ cancel: []; confirm: [] }>()
const { rushHappinessDelta, rushXpPerWorker } = useGameBalance()

const failureChance = computed(() => Math.round(props.quote?.fail_chance ?? 0))
const successChance = computed(() => Math.round(props.quote?.success_chance ?? 0))
const incidentTags = computed(() => rushConsequenceTags(props.quote?.eligible_incidents ?? []))
const successReward = computed(() => {
  const quote = props.quote
  if (!quote) return ''
  const parts: string[] = []
  if (Object.values(quote.payout).some((amount) => amount > 0)) {
    parts.push(formatRushPayout(quote.payout))
  }
  if (rushXpPerWorker.value && rushXpPerWorker.value > 0) {
    parts.push(`+${rushXpPerWorker.value} XP per worker`)
  }
  return parts.join(' · ')
})
const canActivate = computed(
  () => !!props.quote?.can_rush && !props.loading && !props.rushing && !props.error
)
const confirmLabel = computed(() => (props.rushing ? 'Activating...' : 'Activate Rush'))
</script>

<template>
  <TerminalModal
    :open="open"
    :title="`Rush ${roomName}?`"
    icon="mdi:lightning-bolt"
    size="md"
    @close="emit('cancel')"
  >
    <div class="space-y-4 p-6 text-theme-primary">
      <p v-if="loading" class="text-sm text-theme-primary/70">Checking the odds...</p>
      <p v-else-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

      <template v-else-if="quote">
        <div>
          <span class="block text-xs tracking-wider text-theme-primary/60 uppercase">
            Failure chance
          </span>
          <strong class="text-2xl text-warning">{{ failureChance }}%</strong>
        </div>

        <p v-if="successReward" class="text-sm">On success: {{ successReward }}</p>

        <div class="space-y-2">
          <span class="block text-xs tracking-wider text-theme-primary/60 uppercase">
            Possible incidents
          </span>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="tag in incidentTags"
              :key="tag"
              class="rounded border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs text-warning"
            >
              {{ tag }}
            </span>
          </div>
          <p v-if="rushHappinessDelta && rushHappinessDelta > 0" class="text-sm text-danger">
            Failure cost: −{{ rushHappinessDelta }} Happiness
          </p>
        </div>

        <p v-if="!quote.can_rush" class="text-sm text-warning">{{ blockedMessage }}</p>
        <p class="text-xs text-theme-primary/60">Repeated rushes add risk until stacks decay.</p>

        <details class="rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2">
          <summary class="cursor-pointer text-sm">Odds breakdown</summary>
          <dl class="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <dt class="text-theme-primary/60">Success chance</dt>
            <dd class="text-right">{{ successChance }}%</dd>
            <dt class="text-theme-primary/60">SPECIAL (gear)</dt>
            <dd class="text-right">{{ quote.avg_ability.toFixed(1) }}</dd>
            <dt class="text-theme-primary/60">Luck (gear)</dt>
            <dd class="text-right">{{ quote.avg_luck.toFixed(1) }}</dd>
            <dt class="text-theme-primary/60">Workers</dt>
            <dd class="text-right">{{ quote.worker_count }}</dd>
          </dl>
        </details>
      </template>

      <p v-else class="text-sm text-theme-primary/70">Rush details are unavailable.</p>
    </div>

    <template #footer>
      <TerminalModalActions
        cancel-label="Cancel"
        :confirm-label="confirmLabel"
        confirm-icon="mdi:lightning-bolt"
        :confirm-disabled="!canActivate"
        @cancel="emit('cancel')"
        @confirm="emit('confirm')"
      />
    </template>
  </TerminalModal>
</template>
