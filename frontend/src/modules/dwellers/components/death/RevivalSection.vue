<script setup lang="ts">
/**
 * RevivalSection - Component for handling dweller revival actions
 * @component
 */
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import type { RevivalCostResponse } from '@/modules/dwellers/models/dweller'

interface Props {
  dwellerId: string
  revivalCost: RevivalCostResponse | null
  loading?: boolean
}

interface Emits {
  (e: 'revive', id: string): void
}

const { loading = false, dwellerId, revivalCost } = defineProps<Props>()

const emit = defineEmits<Emits>()

const canAfford = computed(() => revivalCost?.can_afford ?? false)

// Calculate progress percentage for days remaining (assuming 7 days max)
const timeProgress = computed(() => {
  if (!revivalCost?.days_until_permanent) return 0
  const days = revivalCost.days_until_permanent
  return Math.min(100, Math.max(0, (days / 7) * 100))
})

const isUrgent = computed(() => {
  return (revivalCost?.days_until_permanent ?? 0) < 3
})

const handleRevive = () => {
  if (canAfford.value && !loading) {
    emit('revive', dwellerId)
  }
}
</script>

<template>
  <Card
    class="revival-section gap-0 rounded-lg border-2 border-theme-primary/40 bg-terminal-background p-6 shadow-glow-md ring-0 crt-screen"
  >
    <div class="mb-4 border-b border-gray-700 pb-4">
      <h3 class="text-xl font-bold terminal-glow text-theme-primary">
        EMERGENCY MEDICAL PROTOCOL
      </h3>
    </div>
    <div v-if="revivalCost" class="flex flex-col gap-4">
      <!-- Cost Analysis -->
      <div class="grid grid-cols-2 gap-4">
        <div class="bg-black/40 border border-theme-primary/30 p-3 rounded">
          <div class="text-xs text-theme-primary/60 uppercase mb-1">Revival Cost</div>
          <div class="flex items-center gap-2 text-xl font-bold text-theme-primary">
            <Icon icon="mdi:bottle-tonic-plus" class="w-5 h-5" />
            <span>{{ revivalCost.revival_cost }}</span>
          </div>
        </div>

        <div
          class="bg-black/40 border border-theme-primary/30 p-3 rounded"
          :class="{ 'border-red-500/50': !canAfford }"
        >
          <div class="text-xs text-theme-primary/60 uppercase mb-1">Vault Funds</div>
          <div
            class="flex items-center gap-2 text-xl font-bold"
            :class="canAfford ? 'text-theme-primary' : 'text-red-500'"
          >
            <Icon icon="mdi:finance" class="w-5 h-5" />
            <span>{{ revivalCost.vault_caps }}</span>
          </div>
        </div>
      </div>

      <!-- Status Message -->
      <div
        v-if="!canAfford"
        class="flex items-center gap-2 text-red-500 text-sm font-bold bg-red-900/10 p-2 rounded border border-red-500/30"
      >
        <Icon icon="mdi:alert-circle" class="w-5 h-5 shrink-0" />
        <span>INSUFFICIENT FUNDS FOR PROCEDURE</span>
      </div>

      <!-- Time Remaining -->
      <div class="space-y-1">
        <div class="flex justify-between text-xs uppercase">
          <span :class="isUrgent ? 'text-red-400 animate-pulse' : 'text-theme-primary/80'">
            Time Until Decomposition
          </span>
          <span class="font-mono">{{ revivalCost.days_until_permanent }} days</span>
        </div>

        <div class="h-2 bg-black/40 border border-theme-primary/30 rounded overflow-hidden">
          <div
            class="h-full transition-all duration-500 shadow-[0_0_8px_currentColor]"
            :class="isUrgent ? 'bg-red-500 text-red-500' : 'bg-theme-primary text-theme-primary'"
            :style="{ width: `${timeProgress}%` }"
          ></div>
        </div>
      </div>

      <!-- Action -->
      <div class="pt-2">
        <p class="text-xs text-center text-theme-primary/60 mb-3 font-mono">
          WARNING: Procedure success guaranteed. Subject will return with full health but radiation
          levels may persist.
        </p>

        <Button
          variant="default"
          size="lg"
          class="w-full"
          :disabled="!canAfford || loading"
          @click="handleRevive"
        >
          <Icon v-if="loading" icon="mdi:loading" class="mr-2 animate-spin" />
          <Icon v-else icon="mdi:flash" class="mr-2" />
          INITIATE REVIVAL SEQUENCE
        </Button>
      </div>
    </div>

    <!-- Loading State Skeleton -->
    <div v-else class="animate-pulse space-y-4 py-4">
      <div class="grid grid-cols-2 gap-4">
        <div class="h-16 bg-theme-primary/10 rounded"></div>
        <div class="h-16 bg-theme-primary/10 rounded"></div>
      </div>
      <div class="h-2 bg-theme-primary/10 rounded mt-4"></div>
      <div class="h-10 bg-theme-primary/10 rounded mt-4"></div>
    </div>
  </Card>
</template>

<style scoped>
/* Additional terminal styling tweaks if needed */
</style>
