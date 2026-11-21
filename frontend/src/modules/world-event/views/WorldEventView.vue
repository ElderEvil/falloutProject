<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { Progress } from '@/core/components/ui/progress'
import { Button } from '@/core/components/ui/button'
import { useCountdown } from '@/core/composables/useCountdown'
import { usePolling } from '@/core/composables/usePolling'
import { useToast } from '@/core/composables/useToast'
import { computeRemainingSeconds, formatDuration } from '@/core/utils/time'
import { useWorldEventStore } from '../stores/worldEvent'

const route = useRoute()
const store = useWorldEventStore()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)

const remainingSeconds = computed(() => {
  const endsAt = store.event?.ends_at
  return endsAt ? computeRemainingSeconds(endsAt, Date.now()) : 0
})
const { secondsLeft } = useCountdown(remainingSeconds)

const countdownLabel = computed(() => {
  if (!store.event?.ends_at) return 'No deadline'
  if (secondsLeft.value <= 0) return 'Ended'
  return formatDuration(secondsLeft.value, { omitZeroHours: true, suffix: 'left' })
})

const progressPercent = computed(() => store.progressPercent)

async function claim() {
  const ok = await store.claim(vaultId.value)
  if (ok) toast.success('World event reward claimed')
}

onMounted(() => store.load(vaultId.value))
usePolling(() => store.load(vaultId.value, { silent: true }), {
  interval: 10_000,
  immediate: false,
})
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <VaultPageShell flicker>
      <PageContentRail class="flex flex-col gap-6">
        <PageHeader
          title="Relay"
          icon="mdi:radio-tower"
          subtitle="Every vault on this server feeds the same signal"
        />

        <TerminalLoadingState
          v-if="store.loading && !store.hasEvent"
          message="Tuning the relay..."
        />

        <div
          v-else-if="!store.hasEvent"
          class="rounded border-2 border-terminal-green/40 bg-surface-raised p-8 text-center"
        >
          <Icon icon="mdi:radio-tower" class="mx-auto mb-3 h-8 w-8 text-terminal-green/50" />
          <p class="text-terminal-green/80">No world event is broadcasting right now.</p>
        </div>

        <template v-else-if="store.event">
          <div class="rounded border-2 border-terminal-green/40 bg-surface-raised p-6">
            <h2 class="text-2xl font-bold">{{ store.event.title }}</h2>
            <p v-if="store.event.description" class="mt-2 text-sm text-terminal-green/80">
              {{ store.event.description }}
            </p>

            <div class="mt-6">
              <div class="mb-1 flex justify-between text-sm">
                <span>{{ store.event.progress_amount }} / {{ store.event.target_amount }}</span>
                <span>{{ progressPercent }}%</span>
              </div>
              <Progress :model-value="progressPercent" label="Event progress" />
            </div>

            <dl class="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div>
                <dt class="text-terminal-green/60">Your contribution</dt>
                <dd class="text-lg font-bold">
                  {{ store.event.contribution }} / {{ store.event.personal_min }}
                </dd>
              </div>
              <div>
                <dt class="text-terminal-green/60">Vaults</dt>
                <dd class="text-lg font-bold">{{ store.event.participant_count }}</dd>
              </div>
              <div>
                <dt class="text-terminal-green/60">Status</dt>
                <dd class="text-lg font-bold">{{ store.event.status ?? 'UNKNOWN' }}</dd>
              </div>
              <div>
                <dt class="text-terminal-green/60">Ends</dt>
                <dd class="text-lg font-bold">{{ countdownLabel }}</dd>
              </div>
            </dl>

            <div class="mt-6 flex items-center gap-4">
              <Button :disabled="!store.event.can_claim || store.claiming" @click="claim">
                {{ store.claiming ? 'Claiming...' : 'Claim reward' }}
              </Button>
              <p v-if="store.claimError" class="text-sm text-danger">{{ store.claimError }}</p>
              <p v-else-if="store.claimed" class="text-sm text-success">Reward claimed.</p>
              <p v-else-if="!store.event.can_claim" class="text-sm text-terminal-green/60">
                Contribute {{ store.event.personal_min }} to qualify.
              </p>
            </div>
          </div>

          <p v-if="store.error" class="text-sm text-danger">{{ store.error }}</p>
        </template>
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>
