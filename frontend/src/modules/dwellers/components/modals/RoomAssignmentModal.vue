<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { Button } from '@/core/components/ui/button'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { producesResources } from '@/modules/rooms/models/roomParts'
import { getTrainingRoomCapacity } from '@/modules/rooms/utils/room'
import { useDwellerStore } from '../../stores/dweller'
import {
  getAbilityConfig,
  getDwellerDisplayName,
  isMature,
  type Dweller,
} from '../../models/dweller'
import { getSpecialBreakdown } from '../../models/specialBreakdown'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'

const props = defineProps<{ open: boolean; dweller: Dweller; vaultId: string }>()
const emit = defineEmits<{ 'update:open': [open: boolean]; assigned: [] }>()
const auth = useAuthStore()
const roomStore = useRoomStore()
const { filter, management } = useDwellerStore()
const toast = useToast()
const selectedId = ref<string | null>(null)
const loading = ref(false)
const loaded = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
let loadSequence = 0

const unavailable = computed(() => {
  if (props.dweller.is_dead) return 'Dead dwellers cannot be assigned.'
  if (['exploring', 'questing'].includes(props.dweller.status))
    return 'This dweller is away from the vault.'
  if (props.dweller.room) return 'Unassign this dweller before choosing a new room.'
  return null
})
const choices = computed(() =>
  roomStore.rooms
    .filter(producesResources)
    .map((room) => {
      const residents = filter.allDwellers.filter((dweller) => dweller.room_id === room.id)
      const workers = residents.filter((dweller) => !dweller.apprentice_stat).length
      const capacity = getTrainingRoomCapacity(room)
      const ability = getAbilityConfig(room.ability)!
      const stat =
        getSpecialBreakdown(props.dweller).find((stat) => stat.letter === ability.letter)
          ?.effective ?? 1
      const restriction =
        unavailable.value ??
        (isMature(props.dweller)
          ? workers >= capacity
            ? 'All worker slots are occupied.'
            : null
          : residents.some((dweller) => dweller.apprentice_stat)
            ? 'This room already has an apprentice.'
            : null)
      return { room, workers, capacity, ability, stat, restriction }
    })
    .sort(
      (a, b) =>
        Number(!!a.restriction) - Number(!!b.restriction) ||
        b.stat - a.stat ||
        a.room.name.localeCompare(b.room.name)
    )
)
const selected = computed(() => choices.value.find((choice) => choice.room.id === selectedId.value))

async function loadChoices() {
  const sequence = ++loadSequence
  selectedId.value = null
  error.value = null
  if (!props.open) return
  loading.value = true
  loaded.value = false
  try {
    if (!auth.token) throw new Error('Sign in again to load rooms.')
    const [roomResult] = await Promise.all([
      roomStore.fetchRooms(props.vaultId, auth.token, true),
      filter.fetchAllDwellers(props.vaultId, auth.token, true),
    ])
    if (sequence !== loadSequence) return
    if (roomResult !== 'loaded') throw new Error('Rooms changed while loading. Try again.')
    loaded.value = true
  } catch (cause) {
    if (sequence === loadSequence)
      error.value = getErrorMessage(cause, 'Could not load rooms. Try again.')
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}
watch(() => [props.open, props.dweller.id, props.vaultId], loadChoices, { immediate: true })

async function assignSelected() {
  const choice = selected.value
  if (!choice || choice.restriction || saving.value || !auth.token) return
  saving.value = true
  error.value = null
  try {
    await management.assignDwellerToRoom(props.dweller.id, choice.room.id, auth.token)
    toast.success(`${getDwellerDisplayName(props.dweller)} assigned to ${choice.room.name}`)
    emit('assigned')
    emit('update:open', false)
  } catch (cause) {
    error.value = getErrorMessage(cause, 'Could not assign this dweller. Try again.')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <TerminalModal
    :open="open"
    title="Choose a production room"
    size="xl"
    max-height="80"
    :show-close="!saving"
    @update:open="!saving && emit('update:open', $event)"
  >
    <div
      class="flex flex-col gap-3 overflow-y-auto overscroll-contain p-5"
      :aria-busy="loading || saving"
    >
      <p class="text-theme-primary">
        {{ getDwellerDisplayName(dweller) }} · {{ isMature(dweller) ? 'Worker' : 'Apprentice' }}
      </p>
      <p class="text-sm text-muted-foreground">
        Compare the SPECIAL each room uses. Highest effective stat appears first. Training, Arena,
        and the Response Station have separate controls.
      </p>
      <p v-if="loading" role="status">Loading rooms and occupancy…</p>
      <div v-else-if="error" role="alert" class="flex flex-col gap-2">
        <p class="text-danger">{{ error }}</p>
        <Button v-if="!saving && !loaded" variant="outline" @click="loadChoices">Try again</Button>
      </div>
      <p v-if="unavailable" role="status">{{ unavailable }}</p>
      <template v-if="!loading && loaded">
        <p v-if="!choices.length" role="status">
          No production rooms yet. Build one in the vault to assign this dweller.
        </p>
        <div v-for="choice in choices" :key="choice.room.id" class="flex flex-col gap-1">
          <Button
            variant="outline"
            class="h-auto w-full whitespace-normal py-3"
            :aria-pressed="selectedId === choice.room.id"
            :aria-label="`${choice.room.name}, tier ${choice.room.tier}, ${choice.ability.label} ${choice.stat}, ${choice.workers} of ${choice.capacity} workers`"
            :aria-describedby="
              choice.restriction ? `room-restriction-${choice.room.id}` : undefined
            "
            :disabled="!!choice.restriction || saving"
            @click="selectedId = choice.room.id"
          >
            <span class="flex w-full flex-wrap items-center justify-between gap-2 text-left">
              <span
                >{{ selectedId === choice.room.id ? '✓ ' : '' }}{{ choice.room.name }} · Tier
                {{ choice.room.tier }}</span
              >
              <span
                >{{ choice.ability.label }} {{ choice.stat }} · {{ choice.workers }}/{{
                  choice.capacity
                }}
                workers</span
              >
            </span>
          </Button>
          <p
            v-if="choice.restriction"
            :id="`room-restriction-${choice.room.id}`"
            class="text-sm text-muted-foreground"
          >
            {{ choice.restriction }}
          </p>
        </div>
      </template>
      <p v-if="selected" role="status" class="text-sm">
        {{ selected.room.name }}: {{ selected.ability.label }} {{ selected.stat }} contributes to
        this room's {{ selected.ability.resourceName.toLowerCase() }} production.
        <template v-if="!isMature(dweller)"
          >As an apprentice, this dweller also trains {{ selected.ability.label }}.</template
        >
        Assignment changes only when you confirm.
      </p>
    </div>
    <template #footer>
      <Button variant="secondary" :disabled="saving" @click="emit('update:open', false)"
        >Cancel</Button
      >
      <Button
        :aria-label="selected ? `Assign to ${selected.room.name}` : 'Select a room'"
        :disabled="loading || saving || !selected || !!selected.restriction"
        @click="assignSelected"
      >
        {{ saving ? 'Assigning…' : selected ? 'Confirm assignment' : 'Select a room' }}
      </Button>
    </template>
  </TerminalModal>
</template>
