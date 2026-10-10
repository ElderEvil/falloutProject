<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Badge } from '@/core/components/ui/badge'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import { useQuestStore } from '@/modules/progression/stores/quest'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { VaultQuest } from '../models/quest'
import { usePartySelection } from '../composables/usePartySelection'
import PartySlots from './party/PartySlots.vue'
import AvailableDwellers from './party/AvailableDwellers.vue'
import SupplySliders from './party/SupplySliders.vue'

interface Props {
  modelValue: boolean
  quest: VaultQuest | null
  vaultId: string
  dwellers: DwellerShort[]
  currentParty: DwellerShort[]
  maxPartySize?: number
  title?: string
  subtitle?: string
  /** Cleared/pending badge state for the subtitle row; absent = plain-text subtitle. */
  subtitleStatus?: 'cleared' | 'pending'
  /** Status text shown inside the badge ('Cleared ×n' / 'Not cleared'). */
  subtitleLabel?: string
  details?: boolean
  showSupplies?: boolean
  maxStimpaks?: number
  maxRadaways?: number
}

const {
  maxPartySize = 3,
  currentParty,
  dwellers,
  modelValue,
  quest,
  vaultId,
  title,
  subtitle,
  subtitleStatus,
  subtitleLabel,
  details = false,
  showSupplies = false,
  maxStimpaks = 0,
  maxRadaways = 0,
} = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'assign', dwellerIds: string[], supplies: { stimpaks: number; radaways: number }): void
  (e: 'start'): void
  (e: 'details'): void
}>()

const questStore = useQuestStore()

// Selection + supply state, shared with the dispatch (location-details) flow.
const {
  selectedDwellerIds,
  selectedStimpaks,
  selectedRadaways,
  stimpakMax,
  radawayMax,
  selectedDwellers,
  canSubmit,
  toggleDweller,
  setStimpaks,
  setRadaways,
  resetOnOpen,
  suppliesPayload,
} = usePartySelection({
  dwellers: () => dwellers,
  maxPartySize: () => maxPartySize,
  maxStimpaks: () => maxStimpaks,
  maxRadaways: () => maxRadaways,
})

const eligibleDwellers = ref<DwellerShort[]>([])
const eligibleDwellersError = ref<string | null>(null)
const isLoadingEligible = ref(false)

// Sync with current party when modal opens
watch(
  () => modelValue,
  async (isOpen) => {
    if (isOpen) {
      resetOnOpen(currentParty.map((d) => d.id))
      eligibleDwellersError.value = null
      // Fetch eligible dwellers for this quest
      if (quest && vaultId) {
        isLoadingEligible.value = true
        try {
          const eligible = await questStore.getEligibleDwellers(vaultId, quest.id)
          eligibleDwellers.value = eligible
            .map((e) => {
              const fullDweller = dwellers.find((d) => d.id === e.id)
              if (fullDweller) return fullDweller
              return {
                ...e,
                status: (e as { status?: string }).status || 'idle',
              } as unknown as DwellerShort
            })
            .filter((d): d is DwellerShort => d !== undefined)
        } catch (error) {
          eligibleDwellersError.value = 'Failed to check eligibility'
          eligibleDwellers.value = []
        } finally {
          isLoadingEligible.value = false
        }
      }
    }
  }
)

// Idle dwellers first (best quest candidates), then by level — status order:
// idle, resting, working, everything else.
const STATUS_ORDER: Record<string, number> = { idle: 0, resting: 1, working: 2 }

const availableDwellers = computed(() => {
  // Quest mode: only eligible dwellers from the API - no fallback to all dwellers.
  // This enforces quest requirements (level, items, etc.).
  // Dispatch mode (no quest): the caller's dweller list is the candidate pool.
  const baseDwellers = quest
    ? eligibleDwellers.value.length > 0
      ? eligibleDwellers.value
      : []
    : dwellers

  return baseDwellers
    .filter((dweller) => {
      // Include if already selected for this quest
      if (selectedDwellerIds.value.includes(dweller.id)) return true

      // Only show idle, working, or resting dwellers (not on other quests)
      return ['idle', 'working', 'resting'].includes(dweller.status)
    })
    .sort((a, b) => {
      const statusDiff = (STATUS_ORDER[a.status] ?? 3) - (STATUS_ORDER[b.status] ?? 3)
      if (statusDiff !== 0) return statusDiff
      return (b.level ?? 0) - (a.level ?? 0)
    })
})

const close = () => {
  emit('update:modelValue', false)
}

const handleAssign = () => {
  emit('assign', selectedDwellerIds.value, suppliesPayload())
}

const handleStart = () => {
  emit('start')
}

const handleAssignAndStart = () => {
  emit('assign', selectedDwellerIds.value, suppliesPayload())
  emit('start')
}
</script>

<template>
  <TerminalModal
    :open="modelValue"
    :title="title ?? (quest ? `Start Quest: ${quest.title}` : 'Dispatch Dweller')"
    size="5xl"
    max-height="80"
    header-class="flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4 pr-12"
    body-class="flex-1 overflow-y-auto px-5 pt-5 pb-5"
    @update:open="emit('update:modelValue', $event)"
  >
      <template #header-extra>
        <Button
          v-if="details"
          variant="outline"
          size="xs"
          type="button"
          class="ml-auto font-mono text-xs font-bold"
          @click="emit('details')"
        >
          Details
        </Button>
      </template>
      <template #subheader>
      <div
        v-if="subtitle || subtitleStatus"
        class="flex flex-wrap items-center gap-2 border-b border-theme-primary/20 px-6 py-2 text-xs text-theme-primary/70"
      >
        <Badge
          v-if="subtitleStatus"
          :variant="subtitleStatus === 'cleared' ? 'default' : 'outline'"
          :class="
            subtitleStatus === 'cleared'
              ? 'border-theme-primary bg-theme-primary/10 text-theme-primary terminal-glow'
              : 'border-warning/60 text-warning'
          "
        >
          <Icon
            :icon="subtitleStatus === 'cleared' ? 'mdi:shield-check' : 'mdi:shield-outline'"
            class="h-3.5 w-3.5"
          />
          {{ subtitleLabel }}
        </Badge>
        <span v-if="subtitle">{{ subtitle }}</span>
      </div>
      </template>

    <div class="party-modal-content">
      <PartySlots
        :selected-dwellers="selectedDwellers"
        :selected-count="selectedDwellerIds.length"
        :max-party-size="maxPartySize"
        @remove="toggleDweller"
      />

      <AvailableDwellers
        :dwellers="availableDwellers"
        :selected-ids="selectedDwellerIds"
        :is-loading="isLoadingEligible"
        :show-eligible-badge="!!quest && eligibleDwellers.length > 0"
        :error="eligibleDwellersError"
        @toggle="toggleDweller"
      />

      <!-- Quest Duration Info -->
      <div v-if="quest && quest.duration_minutes" class="quest-duration">
        <Icon icon="mdi:clock-outline" class="inline-icon" />
        Estimated Duration: {{ quest.duration_minutes }} minutes
      </div>
    </div>

      <SupplySliders
        v-if="showSupplies"
        :selected-stimpaks="selectedStimpaks"
        :selected-radaways="selectedRadaways"
        :max-stimpaks="maxStimpaks"
        :max-radaways="maxRadaways"
        :stimpak-max="stimpakMax"
        :radaway-max="radawayMax"
        @update:stimpaks="setStimpaks"
        @update:radaways="setRadaways"
      />

      <template #footer>
        <TerminalModalActions
          cancel-label="Cancel"
          :confirm-label="quest ? 'Start Quest' : 'Dispatch'"
          confirm-icon="mdi:check"
          :confirm-disabled="!canSubmit"
          @cancel="close"
          @confirm="quest ? handleAssignAndStart() : handleAssign()"
        />
      </template>
  </TerminalModal>
</template>

<style scoped>
.party-modal-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.inline-icon {
  font-size: 1.2rem;
}

.quest-duration {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: rgba(var(--color-theme-primary-rgb), 0.08);
  border: 1px solid var(--color-theme-accent);
  border-radius: 6px;
  color: var(--color-theme-accent);
  font-size: 0.9rem;
}
</style>
