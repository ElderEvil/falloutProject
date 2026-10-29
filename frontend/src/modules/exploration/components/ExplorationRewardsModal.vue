<script setup lang="ts">
import { notifyErrorOnce } from '@/core/utils/errorHandler'
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import RewardCard from '@/core/components/common/RewardCard.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { useExplorationStore, type RewardsSummary } from '@/modules/exploration/stores/exploration'
import ExplorationItemRow from '@/modules/exploration/components/ExplorationItemRow.vue'

interface Props {
  rewards: RewardsSummary | null
  dwellerName: string
  show: boolean
  explorationId?: string
  pendingOnly?: boolean
}

const props = withDefaults(defineProps<Props>(), { explorationId: '', pendingOnly: false })
const toast = useToast()
const authStore = useAuthStore()
const explorationStore = useExplorationStore()

// Guard against null rewards
const safeRewards = computed(
  () =>
    props.rewards || {
      caps: 0,
      items: [],
      overflow_items: [],
      experience: 0,
      distance: 0,
      enemies_defeated: 0,
      events_encountered: 0,
    }
)
const emit = defineEmits<{
  close: [hasUnresolvedOverflow: boolean]
  resolved: []
}>()

// Overflow items live here until each is Taken or Sold; the backend holds the
// source of truth and every action replaces this list from its response.
const unclaimed = ref([...(props.rewards?.overflow_items ?? [])])
watch(
  () => props.rewards,
  (rewards) => {
    unclaimed.value = [...(rewards?.overflow_items ?? [])]
    legacyOverflow.value = false
  }
)

const hasOverflow = computed(() => unclaimed.value.length > 0)
const resolvedExplorationId = computed(
  () => safeRewards.value.exploration_id || props.explorationId
)
const busyIndex = ref<number | null>(null)
const legacyOverflow = ref(false)
const requiresResolution = computed(() => hasOverflow.value && !legacyOverflow.value)

const resolveOverflow = async (action: 'take' | 'sell', index: number, notify = true) => {
  if (!resolvedExplorationId.value || !authStore.token || busyIndex.value !== null) return undefined
  const name = unclaimed.value[index]?.item_name ?? 'Item'
  busyIndex.value = index
  try {
    const result = await explorationStore.resolveOverflowItem(
      resolvedExplorationId.value,
      action,
      index
    )
    unclaimed.value = result.unclaimed_loot
    emit('resolved')
    if (notify)
      toast.success(
        action === 'take' ? `Stored ${name}` : `Sold ${name} for +${result.caps_granted} caps`
      )
    return result
  } catch (error) {
    const status =
      (error as { status?: number | null }).status ??
      (error as { response?: { status?: number } }).response?.status
    if (status === 404) {
      legacyOverflow.value = true
      toast.info('These items were left behind before overflow resolution was available')
      return undefined
    }
    notifyErrorOnce(error, action === 'take' ? 'Could not take item' : 'Could not sell item')
    return undefined
  } finally {
    busyIndex.value = null
  }
}

const reportBulkSale = (sold: number, caps: number) => {
  if (sold) toast.success(`Sold ${sold} item${sold === 1 ? '' : 's'} for +${caps} caps`)
}

const sellAll = async () => {
  let sold = 0
  let caps = 0
  while (unclaimed.value.length > 0) {
    const result = await resolveOverflow('sell', 0, false)
    if (!result) {
      reportBulkSale(sold, caps)
      return
    }
    sold++
    caps += result.caps_granted
  }
  reportBulkSale(sold, caps)
}

const tryClose = () => emit('close', requiresResolution.value)
</script>

<template>
  <TerminalModal
    :open="show"
    title="Exploration Complete!"
    icon="mdi:treasure-chest"
    size="xl"
    max-height="75"
    @close="tryClose"
  >
    <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
      <!-- Dweller Name -->
      <div
        class="mb-6 flex items-center gap-2 rounded border border-theme-primary/20 bg-theme-primary/5 p-4 text-lg font-semibold text-theme-primary"
      >
        <Icon icon="mdi:account-check" class="h-6 w-6 shrink-0" />
        {{ dwellerName }} has returned from the wasteland!
      </div>

      <!-- Recalled Early Banner -->
      <div
        v-if="safeRewards.recalled_early"
        class="mb-6 flex items-center gap-2 rounded border border-warning/30 bg-warning/10 p-3 text-sm text-warning"
      >
        <Icon icon="mdi:information" class="h-6 w-6 shrink-0" />
        Recalled early ({{ Math.round(safeRewards.progress_percentage || 0) }}% complete) - Reduced
        rewards
      </div>

      <!-- Rewards Grid -->
      <div
        v-if="!pendingOnly"
        class="mb-8 grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4"
      >
        <RewardCard
          icon="mdi:star"
          label="Experience Gained"
          :value="`+${safeRewards.experience} XP`"
          variant="experience"
          span
        />
        <RewardCard
          icon="mdi:coins"
          label="Bottle Caps"
          :value="String(safeRewards.caps)"
          variant="caps"
          span
        />
        <RewardCard
          icon="mdi:map-marker-distance"
          label="Distance Traveled"
          :value="`${safeRewards.distance} miles`"
          variant="distance"
        />
        <RewardCard
          icon="mdi:skull"
          label="Enemies Defeated"
          :value="String(safeRewards.enemies_defeated)"
          variant="enemies"
        />
        <RewardCard
          icon="mdi:map-marker-alert"
          label="Events Encountered"
          :value="String(safeRewards.events_encountered)"
          variant="events"
        />
      </div>

      <!-- Items Found -->
      <div v-if="safeRewards.items && safeRewards.items.length > 0" class="mt-6">
        <h3 class="panel-header text-lg font-bold text-theme-primary">
          <span class="flex items-center gap-2">
            <Icon icon="mdi:package-variant" />
            {{ requiresResolution ? 'Stored in Vault' : 'Items Found' }}
          </span>
        </h3>
        <div class="flex flex-col gap-3">
          <ExplorationItemRow v-for="(item, index) in safeRewards.items" :key="index" :item="item">
            <Icon icon="mdi:check-circle" class="h-6 w-6 shrink-0 text-theme-primary" />
          </ExplorationItemRow>
        </div>
      </div>

      <div
        v-else-if="!hasOverflow"
        class="flex flex-col items-center justify-center gap-4 px-8 py-12 text-theme-primary/50"
      >
        <Icon icon="mdi:package-variant-closed" class="h-16 w-16" />
        <p>No items found during this exploration</p>
      </div>

      <!-- Overflow Items (Storage Full) -->
      <div v-if="hasOverflow" class="mt-6">
        <h3 class="panel-header text-lg font-bold text-theme-primary">
          <span class="flex items-center gap-2">
            <Icon icon="mdi:package-variant-closed-remove" />
            {{
              legacyOverflow ? 'Storage Full — Items Left Behind' : 'Storage Full — Needs Decision'
            }}
          </span>
        </h3>
        <p v-if="legacyOverflow" class="text-sm text-theme-primary/70">
          This report predates overflow resolution. These items were left behind.
        </p>
        <div v-else class="flex flex-col gap-3">
          <ExplorationItemRow
            v-for="(item, index) in unclaimed"
            :key="`${item.item_name}-${index}`"
            :item="item"
          >
            <div class="overflow-actions flex shrink-0 gap-2">
              <Button
                size="sm"
                :disabled="busyIndex !== null"
                @click="resolveOverflow('take', index)"
              >
                <Icon v-if="busyIndex === index" icon="mdi:loading" class="animate-spin" />
                Take
              </Button>
              <Button
                size="sm"
                variant="secondary"
                :disabled="busyIndex !== null"
                @click="resolveOverflow('sell', index)"
              >
                Sell
              </Button>
            </div>
          </ExplorationItemRow>
          <Button
            v-if="unclaimed.length > 1"
            size="sm"
            variant="secondary"
            class="sell-all-btn self-end"
            :disabled="busyIndex !== null"
            @click="sellAll"
          >
            Sell all remaining
          </Button>
        </div>
      </div>
    </div>

    <template #footer>
      <Button variant="default" class="collect-btn w-full" @click="tryClose">
        <Icon :icon="hasOverflow ? 'mdi:clock-outline' : 'mdi:check-bold'" />
        {{ hasOverflow ? 'Resolve Later' : 'Collect Rewards' }}
      </Button>
    </template>
  </TerminalModal>
</template>
