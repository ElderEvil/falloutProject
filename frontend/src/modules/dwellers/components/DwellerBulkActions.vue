<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import { useDwellerStore } from '../stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'

interface Props {
  vaultId: string
}

const props = defineProps<Props>()
const { filter: filterStore, management: dwellerStore } = useDwellerStore()
const authStore = useAuthStore()

const unassigningAll = ref(false)
const autoAssigningProduction = ref(false)
const autoAssigning = ref(false)
const showConfirmDialog = ref(false)

/**
 * Idle adults without a room among the currently fetched (already filtered)
 * dwellers — the pool the backend will actually assign from.
 */
const eligibleCount = computed(
  () =>
    filterStore.dwellersWithStatus.filter(
      (dweller) => dweller.status === 'idle' && !dweller.room_id && dweller.age_group === 'adult'
    ).length
)

const activeAgeFilter = computed(() =>
  filterStore.filterAgeGroup !== 'all' ? filterStore.filterAgeGroup : undefined
)

const emptyHint = 'No idle adult dwellers match the current filters'

const filterNote = computed(() => {
  const parts = [filterStore.filterAgeGroup, filterStore.filterStatus].filter((f) => f !== 'all')
  return parts.length ? ` matching the current filters (${parts.join(', ')})` : ''
})

const plural = computed(() => (eligibleCount.value === 1 ? '' : 's'))

const productionTooltip = computed(() =>
  eligibleCount.value === 0
    ? emptyHint
    : `Assign ${eligibleCount.value} idle dweller${plural.value}${filterNote.value} to production rooms by best SPECIAL. Rooms can fill up, so fewer may be assigned.`
)

const allRoomsTooltip = computed(() =>
  eligibleCount.value === 0
    ? emptyHint
    : `Assign ${eligibleCount.value} idle dweller${plural.value}${filterNote.value} across all room types (production, med/science, radio, training) by best SPECIAL. Rooms can fill up, so fewer may be assigned.`
)

const handleUnassignAll = async () => {
  if (!authStore.token) return

  unassigningAll.value = true
  try {
    await dwellerStore.unassignAllDwellers(props.vaultId, authStore.token)
  } finally {
    unassigningAll.value = false
    showConfirmDialog.value = false
  }
}

const handleAutoAssignProduction = async () => {
  if (!authStore.token) return

  autoAssigningProduction.value = true
  try {
    await dwellerStore.autoAssignProductionDwellers(props.vaultId, authStore.token, {
      ageGroup: activeAgeFilter.value,
    })
  } finally {
    autoAssigningProduction.value = false
  }
}

const handleAutoAssignAll = async () => {
  if (!authStore.token) return

  autoAssigning.value = true
  try {
    await dwellerStore.autoAssignAllDwellers(props.vaultId, authStore.token, {
      ageGroup: activeAgeFilter.value,
    })
  } finally {
    autoAssigning.value = false
  }
}
</script>

<template>
  <div class="bulk-actions-toolbar">
    <UTooltip :text="allRoomsTooltip">
      <UButton
        variant="primary"
        size="sm"
        @click="handleAutoAssignAll"
        :loading="autoAssigning"
        :disabled="eligibleCount === 0"
      >
        <Icon icon="mdi:auto-mode" class="h-4 w-4 mr-2" />
        Auto-Assign All Rooms
        <span class="action-count on-primary">{{ eligibleCount }}</span>
      </UButton>
    </UTooltip>

    <UTooltip :text="productionTooltip">
      <UButton
        variant="secondary"
        size="sm"
        @click="handleAutoAssignProduction"
        :loading="autoAssigningProduction"
        :disabled="eligibleCount === 0"
      >
        <Icon icon="mdi:factory" class="h-4 w-4 mr-2" />
        Auto-Assign Production
        <span class="action-count on-secondary">{{ eligibleCount }}</span>
      </UButton>
    </UTooltip>

    <UTooltip text="Remove every dweller from their current room assignments">
      <UButton
        variant="secondary"
        size="sm"
        class="unassign-btn"
        @click="showConfirmDialog = true"
        :loading="unassigningAll"
      >
        <Icon icon="mdi:account-remove" class="h-4 w-4 mr-2" />
        Unassign All Dwellers
      </UButton>
    </UTooltip>

    <!-- Confirmation Dialog -->
    <Teleport to="body">
      <div v-if="showConfirmDialog" class="confirmation-overlay" @click="showConfirmDialog = false">
        <div class="confirmation-dialog" @click.stop>
          <div class="flicker">
            <h3>Unassign All Dwellers?</h3>
            <p>This will remove all dwellers from their current room assignments.</p>
            <div class="dialog-actions">
              <UButton variant="secondary" @click="showConfirmDialog = false">Cancel</UButton>
              <UButton variant="danger" @click="handleUnassignAll" :loading="unassigningAll"
                >Confirm</UButton
              >
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.bulk-actions-toolbar {
  display: flex;
  gap: 0.75rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.5rem;
  margin-bottom: 1.5rem;
}

/* Informational count — full contrast, never out-glows its button (styleguide emphasis scale) */
.action-count {
  margin-left: 0.375rem;
  padding: 0 0.45rem;
  border-radius: 9999px;
  font-size: 0.6875rem;
  font-weight: bold;
}

/* Dark pill inside the solid green primary button */
.on-primary {
  background: rgba(0, 0, 0, 0.4);
  color: var(--color-theme-primary);
}

/* Tinted pill inside the outlined secondary button */
.on-secondary {
  background: var(--color-theme-glow);
  color: var(--color-theme-primary);
}

/* Muted danger, same treatment as the Destroy Room button */
.unassign-btn {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.unassign-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--color-danger) 12%, transparent);
  box-shadow: none;
}

.confirmation-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirmation-dialog {
  background: rgba(0, 0, 0, 0.95);
  border: 2px solid var(--color-theme-primary);
  border-radius: 0.5rem;
  padding: 2rem;
  max-width: 400px;
  box-shadow: 0 0 30px var(--color-theme-glow);
}

.confirmation-dialog h3 {
  color: var(--color-theme-primary);
  margin-bottom: 1rem;
  font-size: 1.25rem;
  font-weight: bold;
  text-transform: uppercase;
}

.confirmation-dialog p {
  color: var(--color-theme-primary);
  opacity: 0.8;
  margin-bottom: 1.5rem;
}

.dialog-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.flicker {
  animation: flicker 0.15s infinite;
}

@keyframes flicker {
  0% {
    opacity: 0.97;
  }
  5% {
    opacity: 0.95;
  }
  10% {
    opacity: 0.9;
  }
  15% {
    opacity: 0.95;
  }
  20% {
    opacity: 0.98;
  }
  25% {
    opacity: 0.95;
  }
  30% {
    opacity: 0.9;
  }
  35% {
    opacity: 0.95;
  }
  40% {
    opacity: 0.98;
  }
  45% {
    opacity: 1;
  }
  50% {
    opacity: 0.98;
  }
  55% {
    opacity: 0.95;
  }
  60% {
    opacity: 0.9;
  }
  65% {
    opacity: 0.95;
  }
  70% {
    opacity: 0.98;
  }
  75% {
    opacity: 0.95;
  }
  80% {
    opacity: 0.9;
  }
  85% {
    opacity: 0.95;
  }
  90% {
    opacity: 0.98;
  }
  95% {
    opacity: 0.95;
  }
  100% {
    opacity: 0.98;
  }
}
</style>
