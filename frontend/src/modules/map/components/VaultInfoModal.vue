<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import type { VaultWithNumbers } from '@/modules/vault/stores/vault'
import type { PlayerVaultMarkerRead } from '../models/map'
import { formatDateTime } from '@/core/utils/format'

interface Props {
  vault: VaultWithNumbers | null
  /** Discovery marker for a real player vault, so the panel can name its owner. */
  marker?: PlayerVaultMarkerRead | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), { marker: null, loading: false })

// Single open-state contract: the parent owns visibility via v-model:open.
const open = defineModel<boolean>('open', { required: true })

const modalTitle = computed(() => {
  const number = props.vault?.number ?? props.marker?.number
  return number ? `Vault ${number}` : 'Vault Record'
})

const updatedAt = computed(() => (props.vault ? formatDateTime(props.vault.updated_at) : ''))
const markerCoords = computed(() =>
  props.marker ? `${props.marker.coord_x}, ${props.marker.coord_y}` : 'Unavailable'
)

// Local descriptor list so the three resource rows share one template block.
const RESOURCE_ROWS = [
  { key: 'power', icon: 'mdi:flash', label: 'Power' },
  { key: 'food', icon: 'mdi:silverware', label: 'Food' },
  { key: 'water', icon: 'mdi:water', label: 'Water' },
] as const

// Mirrors HomeView's card helper so both surfaces render the same fill.
const resourcePercentage = (current: number, maximum: number) =>
  maximum > 0 ? (current / maximum) * 100 : 0
</script>

<template>
  <TerminalModal v-model:open="open" :title="modalTitle" size="3xl" max-height="75">
    <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
      <TerminalLoadingState v-if="loading" message="Accessing vault records..." />

      <TerminalEmptyState
        v-else-if="!vault && !marker"
        icon="mdi:alert-circle-outline"
        title="Vault unavailable"
        description="This vault's record could not be loaded. Close the panel and try again from the map."
        compact
      />

      <div v-else-if="!vault" class="space-y-4">
        <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">VAULT SIGNAL</p>
        <div class="rounded border border-theme-primary/20 bg-surface-sunken p-4">
          <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">OVERSEER</p>
          <p class="mt-1 text-lg font-bold">
            {{ marker?.owner_username }}
            <span v-if="marker?.is_mine" class="text-theme-primary/60">(you)</span>
          </p>
          <p class="mt-2 text-sm leading-6 text-theme-primary/75">
            <template v-if="marker?.is_mine">This is your vault.</template>
            <template v-else>
              This vault belongs to {{ marker?.owner_username }}. Its resources stay private to its
              overseer; only the vault and its owner are shared on the atlas.
            </template>
          </p>
          <div class="mt-4 grid grid-cols-2 gap-3 border-t border-theme-primary/20 pt-4">
            <TerminalMetric
              icon="mdi:map-marker"
              label="MAP COORDINATES"
              :value="markerCoords"
              compact
            />
            <TerminalMetric
              icon="mdi:pound-box-outline"
              label="VAULT NUMBER"
              :value="marker?.number ?? ''"
              compact
            />
          </div>
        </div>
      </div>

      <div v-else class="space-y-4">
        <div
          v-if="marker"
          class="flex items-center justify-between gap-3 border-b border-theme-primary/20 pb-3"
        >
          <span class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">OVERSEER</span>
          <span class="text-sm font-bold">
            {{ marker.owner_username }}
            <span v-if="marker.is_mine" class="text-theme-primary/60">(you)</span>
          </span>
        </div>

        <p class="text-right text-xs text-theme-primary/60">Updated {{ updatedAt }}</p>

        <div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <TerminalMetric
            icon="mdi:coins"
            label="Caps"
            :value="vault.bottle_caps"
            tone="caps"
            compact
          />
          <TerminalMetric
            icon="mdi:emoticon-happy-outline"
            label="Happiness"
            :value="`${vault.happiness}%`"
            compact
          />
          <TerminalMetric
            icon="mdi:office-building"
            label="Rooms"
            :value="vault.room_count"
            compact
          />
          <TerminalMetric
            icon="mdi:account-group"
            label="Dwellers"
            :value="vault.dweller_count"
            compact
          />
        </div>

        <div class="grid grid-cols-2 gap-3 border-t border-theme-primary/20 pt-4 lg:grid-cols-3">
          <div v-for="row in RESOURCE_ROWS" :key="row.key" class="grid gap-1.5">
            <span><Icon :icon="row.icon" /> {{ row.label }}</span>
            <strong>{{ vault[row.key] }} / {{ vault[`${row.key}_max`] }}</strong>
            <Progress
              :model-value="resourcePercentage(vault[row.key], vault[`${row.key}_max`])"
              :label="row.label"
              class="h-1.5"
            />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" size="sm" @click="open = false">Close</Button>
    </template>
  </TerminalModal>
</template>
