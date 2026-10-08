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

interface Props {
  open: boolean
  vault: VaultWithNumbers | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), { loading: false })

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'close'): void
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value: boolean) => emit('update:open', value),
})

const modalTitle = computed(() => (props.vault ? `Vault ${props.vault.number}` : 'Vault Record'))

const updatedAt = computed(() =>
  props.vault ? new Date(props.vault.updated_at).toLocaleString() : ''
)

// Mirrors HomeView's card helper so both surfaces render the same fill.
const resourcePercentage = (current: number, maximum: number) =>
  maximum > 0 ? (current / maximum) * 100 : 0

function closeModal() {
  isOpen.value = false
  emit('close')
}
</script>

<template>
  <TerminalModal
    :open="isOpen"
    :title="modalTitle"
    size="3xl"
    max-height="75"
    @update:open="isOpen = $event"
    @close="emit('close')"
  >
    <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
      <TerminalLoadingState v-if="loading" message="Accessing vault records..." />

      <TerminalEmptyState
        v-else-if="!vault"
        icon="mdi:alert-circle-outline"
        title="Vault unavailable"
        description="This vault's record could not be loaded. Close the panel and try again from the map."
        compact
      />

      <div v-else class="space-y-4">
        <p class="text-right text-xs text-theme-primary/60">Updated {{ updatedAt }}</p>

        <div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <TerminalMetric
            icon="mdi:currency-usd"
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
          <div class="grid gap-1.5">
            <span><Icon icon="mdi:flash" /> Power</span>
            <strong>{{ vault.power }} / {{ vault.power_max }}</strong>
            <Progress
              :model-value="resourcePercentage(vault.power, vault.power_max)"
              label="Power"
              class="h-1.5"
            />
          </div>
          <div class="grid gap-1.5">
            <span><Icon icon="mdi:food" /> Food</span>
            <strong>{{ vault.food }} / {{ vault.food_max }}</strong>
            <Progress
              :model-value="resourcePercentage(vault.food, vault.food_max)"
              label="Food"
              class="h-1.5"
            />
          </div>
          <div class="grid gap-1.5">
            <span><Icon icon="mdi:water" /> Water</span>
            <strong>{{ vault.water }} / {{ vault.water_max }}</strong>
            <Progress
              :model-value="resourcePercentage(vault.water, vault.water_max)"
              label="Water"
              class="h-1.5"
            />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" size="sm" @click="closeModal">Close</Button>
    </template>
  </TerminalModal>
</template>
