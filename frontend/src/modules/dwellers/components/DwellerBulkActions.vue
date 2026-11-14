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
import { useDwellerStore } from '../stores/dweller'
import { ADULT_AGE_GROUPS, type DwellerShort } from '../models/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { isCraftingRoom, isTrainingRoom } from '@/modules/rooms/models/roomParts'
import { useBlockingOverlay } from '@/core/composables/useBlockingOverlay'

interface Props {
  vaultId: string
}

const props = defineProps<Props>()
const { filter: filterStore, management: dwellerStore } = useDwellerStore()
const authStore = useAuthStore()
const roomStore = useRoomStore()

const unassigningAll = ref(false)
const autoAssigning = ref<'all' | 'production' | 'training' | 'crafting' | null>(null)
const showConfirmDialog = ref(false)
useBlockingOverlay(() => showConfirmDialog.value)

/**
 * Counted from the unfiltered roster: the backend receives only the age filter, so a
 * status/focus/rarity narrowing of the view must not shrink the number it assigns.
 */
const rosterForCounts = computed(() =>
  filterStore.allDwellersLoadedVaultId === props.vaultId
    ? filterStore.allDwellers
    : filterStore.dwellers
)

const matchesAgeFilter = (dweller: DwellerShort) => {
  const ageFilter = filterStore.filterAgeGroup
  return ageFilter === 'all' || dweller.age_group === ageFilter
}

const idleInScope = computed(() =>
  rosterForCounts.value.filter(
    (dweller) => dweller.status === 'idle' && !dweller.room_id && matchesAgeFilter(dweller)
  )
)

/** Training and crafting place workers only; the other runs also place youth apprentices. */
const eligibleByTarget = computed(() => {
  const workers = idleInScope.value.filter((dweller) =>
    ADULT_AGE_GROUPS.has(dweller.age_group)
  ).length
  return {
    all: idleInScope.value.length,
    production: idleInScope.value.length,
    training: workers,
    crafting: workers,
  }
})

const activeAgeFilter = computed(() =>
  filterStore.filterAgeGroup !== 'all' ? filterStore.filterAgeGroup : undefined
)

const hasTrainingRooms = computed(() => roomStore.rooms.some((room) => isTrainingRoom(room)))
const hasCraftingRooms = computed(() => roomStore.rooms.some((room) => isCraftingRoom(room)))

const emptyHint = 'No idle dwellers without a room match the current age filter'

const filterNote = computed(() =>
  filterStore.filterAgeGroup !== 'all'
    ? ` matching the ${filterStore.filterAgeGroup} age filter`
    : ''
)

const pluralFor = (count: number) => (count === 1 ? '' : 's')

const productionTooltip = computed(() =>
  eligibleByTarget.value.production === 0
    ? emptyHint
    : `Assign ${eligibleByTarget.value.production} idle dweller${pluralFor(eligibleByTarget.value.production)}${filterNote.value} to production rooms by best SPECIAL. Rooms can fill up, so fewer may be assigned.`
)

const allRoomsTooltip = computed(() =>
  eligibleByTarget.value.all === 0
    ? emptyHint
    : `Assign ${eligibleByTarget.value.all} idle dweller${pluralFor(eligibleByTarget.value.all)}${filterNote.value} across all room types (production, med/science, radio, training, crafting) by best SPECIAL. Rooms can fill up, so fewer may be assigned.`
)

const trainingTooltip = computed(() =>
  eligibleByTarget.value.training === 0
    ? emptyHint
    : `Assign ${eligibleByTarget.value.training} idle dweller${pluralFor(eligibleByTarget.value.training)}${filterNote.value} to training rooms, prioritizing each room's lowest eligible SPECIAL stat.`
)

const craftingTooltip = computed(() =>
  eligibleByTarget.value.crafting === 0
    ? emptyHint
    : `Assign ${eligibleByTarget.value.crafting} idle dweller${pluralFor(eligibleByTarget.value.crafting)}${filterNote.value} to crafting rooms, prioritizing the highest total SPECIAL.`
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

const bulkAssignActions = {
  all: 'autoAssignAllDwellers',
  production: 'autoAssignProductionDwellers',
  training: 'autoAssignTrainingDwellers',
  crafting: 'autoAssignCraftingDwellers',
} as const

const handleAutoAssign = async (target: keyof typeof bulkAssignActions) => {
  if (!authStore.token) return

  autoAssigning.value = target
  try {
    await dwellerStore[bulkAssignActions[target]](props.vaultId, authStore.token, {
      ageGroup: activeAgeFilter.value,
    })
  } finally {
    autoAssigning.value = null
  }
}
</script>

<template>
  <div class="bulk-actions-toolbar">
    <TooltipProvider :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="default"
            size="sm"
            class="border-2 border-theme-primary"
            @click="handleAutoAssign('all')"
            :disabled="autoAssigning === 'all' || eligibleByTarget.all === 0"
          >
            <Icon
              :icon="autoAssigning === 'all' ? 'mdi:loading' : 'mdi:auto-mode'"
              class="h-4 w-4 mr-2"
              :class="{ 'animate-spin': autoAssigning === 'all' }"
            />
            Assign All Rooms
            <span class="action-count on-primary">{{ eligibleByTarget.all }}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{{ allRoomsTooltip }}</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="secondary"
            size="sm"
            class="border-2 border-theme-primary"
            @click="handleAutoAssign('production')"
            :disabled="autoAssigning === 'production' || eligibleByTarget.production === 0"
          >
            <Icon
              :icon="autoAssigning === 'production' ? 'mdi:loading' : 'mdi:factory'"
              class="h-4 w-4 mr-2"
              :class="{ 'animate-spin': autoAssigning === 'production' }"
            />
            Assign Production
            <span class="action-count on-secondary">{{ eligibleByTarget.production }}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{{ productionTooltip }}</TooltipContent>
      </Tooltip>

      <Tooltip v-if="hasTrainingRooms">
        <TooltipTrigger as-child>
          <Button
            variant="secondary"
            size="sm"
            class="border-2 border-theme-primary"
            @click="handleAutoAssign('training')"
            :disabled="autoAssigning === 'training' || eligibleByTarget.training === 0"
          >
            <Icon
              :icon="autoAssigning === 'training' ? 'mdi:loading' : 'mdi:dumbbell'"
              class="h-4 w-4 mr-2"
              :class="{ 'animate-spin': autoAssigning === 'training' }"
            />
            Assign Training
            <span class="action-count on-secondary">{{ eligibleByTarget.training }}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{{ trainingTooltip }}</TooltipContent>
      </Tooltip>

      <Tooltip v-if="hasCraftingRooms">
        <TooltipTrigger as-child>
          <Button
            variant="secondary"
            size="sm"
            class="border-2 border-theme-primary"
            @click="handleAutoAssign('crafting')"
            :disabled="autoAssigning === 'crafting' || eligibleByTarget.crafting === 0"
          >
            <Icon
              :icon="autoAssigning === 'crafting' ? 'mdi:loading' : 'mdi:hammer-wrench'"
              class="h-4 w-4 mr-2"
              :class="{ 'animate-spin': autoAssigning === 'crafting' }"
            />
            Assign Crafting
            <span class="action-count on-secondary">{{ eligibleByTarget.crafting }}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{{ craftingTooltip }}</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="destructive"
            size="sm"
            class="border-2 border-theme-primary"
            @click="showConfirmDialog = true"
            :disabled="unassigningAll"
          >
            <Icon
              :icon="unassigningAll ? 'mdi:loading' : 'mdi:account-remove'"
              class="h-4 w-4 mr-2"
              :class="{ 'animate-spin': unassigningAll }"
            />
            Unassign All Dwellers
          </Button>
        </TooltipTrigger>
        <TooltipContent>Remove every dweller from their current room assignments</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <!-- Confirmation Dialog -->
    <Teleport to="body">
      <div v-if="showConfirmDialog" class="confirmation-overlay" @click="showConfirmDialog = false">
        <div class="confirmation-dialog" @click.stop>
          <div class="flicker">
            <h3>Unassign All Dwellers?</h3>
            <p>This will remove all dwellers from their current room assignments.</p>
            <div class="dialog-actions">
              <Button variant="secondary" @click="showConfirmDialog = false">Cancel</Button>
              <Button variant="destructive" @click="handleUnassignAll" :disabled="unassigningAll"
                >Confirm</Button
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
</style>
