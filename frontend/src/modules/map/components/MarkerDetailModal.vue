<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/core/components/ui/dialog'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '../models/map'
import { useMapStore } from '../stores/map'

interface Props {
  modelValue: boolean
  location: WastelandLocationWithDwellers | null
  vaultMarker: VaultMarkerRead | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const router = useRouter()
const route = useRoute()
const mapStore = useMapStore()

const vaultId = computed(() => route.params.id as string)

// The marker's site-type archetype, when the place maps to a catalog group.
const placeGroup = computed(() => {
  const key = props.location?.group_key
  return key ? (mapStore.placeGroupByKey.get(key) ?? null) : null
})

const isOpen = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const isVaultMarker = computed(() => props.vaultMarker !== null && props.location === null)

const placeName = computed(() => {
  if (props.location) return props.location.name
  if (props.vaultMarker) return props.vaultMarker.name
  return ''
})

const placeType = computed(() => {
  if (props.location) return props.location.type
  if (props.vaultMarker) return 'vault'
  return ''
})

const description = computed(() => {
  if (props.location) return props.location.description ?? 'No description available.'
  if (props.vaultMarker) return props.vaultMarker.description
  return ''
})

const coordinates = computed(() => {
  const marker = props.location ?? props.vaultMarker
  return marker ? `${marker.coord_x}, ${marker.coord_y}` : 'Unavailable'
})

const recordStatus = computed(() => {
  if (isVaultMarker.value) return 'SIGNAL DETECTED'
  return props.location?.is_unlocked ? 'SURVEYED' : 'UNVERIFIED'
})

const recordedAt = computed(() => {
  if (!props.location?.created_at) return 'NO DATE LOGGED'
  return new Date(props.location.created_at).toLocaleDateString()
})

const dwellers = computed(() => {
  if (props.location && props.location.dwellers.length > 0) {
    return props.location.dwellers
  }
  return null
})

const badgeVariant = computed(() => {
  const map: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    home_vault: 'default',
    origin: 'outline',
    visited: 'secondary',
    discovery: 'outline',
    vault: 'destructive',
  }
  return map[placeType.value] ?? 'secondary'
})

// `discovery` has no shadcn amber equivalent; preserve its warning colour explicitly.
const badgeClass = computed(() =>
  placeType.value === 'discovery' ? 'bg-warning text-black border-warning' : ''
)

const isLocked = computed(
  () =>
    props.location !== null && props.location.type !== 'home_vault' && !props.location.is_unlocked
)

const modalTitle = computed(() => {
  if (isLocked.value) return 'Unknown Location'
  return placeName.value
})

function goToDweller(dwellerId: string) {
  isOpen.value = false
  router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}

function goToDwellerChat(dwellerId: string) {
  isOpen.value = false
  router.push(`/dweller/${dwellerId}/chat`)
}

function dwellerDisplayName(first: string, last: string | null) {
  return last ? `${first} ${last}` : first
}
</script>

<template>
  <Dialog :open="isOpen" @update:open="(open) => { isOpen = open }">
    <DialogContent
      class="flex max-h-[75vh] w-full max-w-xl flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-xl"
    >
      <DialogHeader
        class="flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
      >
        <DialogTitle class="text-2xl font-bold text-theme-primary terminal-glow">{{ modalTitle }}</DialogTitle>
      </DialogHeader>
      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
    <div v-if="isLocked" class="flex flex-col items-center py-6 text-center">
      <Icon icon="mdi:lock-question" class="h-16 w-16 text-theme-primary/40" />
      <h3 class="mt-4 text-lg font-bold text-theme-primary">Unknown Location</h3>
      <p class="mt-2 max-w-sm text-sm leading-6 text-theme-primary/60">
        Chat with a dweller who has been here to uncover this place.
      </p>
      <div v-if="dwellers" class="mt-4 w-full max-w-sm space-y-1.5 text-left">
        <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">KNOWN CONTACTS</p>
        <button
          v-for="d in dwellers"
          :key="d.dweller_id"
          type="button"
          class="dweller-contact flex w-full items-center justify-between gap-3 rounded border border-theme-primary/20 bg-surface px-3 py-2 text-left transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
          @click="goToDwellerChat(d.dweller_id)"
        >
          <span class="text-sm text-theme-primary underline underline-offset-2">{{ dwellerDisplayName(d.first_name, d.last_name) }}</span>
          <Icon icon="mdi:message-text-outline" class="h-4 w-4 text-theme-primary/60" />
        </button>
      </div>
    </div>
    <div v-else class="space-y-5">
      <section class="rounded border border-theme-primary/20 bg-surface-sunken p-4">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-xs font-bold tracking-[0.14em] text-theme-primary/60">WASTELAND FIELD REPORT</p>
            <p class="mt-1 text-sm font-bold text-theme-primary">{{ recordStatus }}</p>
          </div>
          <div class="flex flex-col items-end gap-1.5">
            <Badge :variant="badgeVariant" :class="badgeClass">{{ placeType }}</Badge>
            <span
              v-if="placeGroup"
              class="flex items-center gap-1 text-xs text-theme-primary/70"
              :title="placeGroup.description"
            >
              <Icon :icon="placeGroup.icon" class="h-3.5 w-3.5" />
              {{ placeGroup.label }}
            </span>
          </div>
        </div>
        <div class="mt-4 grid grid-cols-2 gap-3">
          <TerminalMetric icon="mdi:map-marker" label="MAP COORDINATES" :value="coordinates" compact />
          <TerminalMetric icon="mdi:radar" label="STATUS" :value="recordStatus" compact />
          <TerminalMetric icon="mdi:calendar-outline" label="RECORDED" :value="recordedAt" compact />
          <TerminalMetric
            :icon="isVaultMarker ? 'mdi:radio-tower' : 'mdi:account-group'"
            :label="isVaultMarker ? 'MARKER TYPE' : 'KNOWN DWELLERS'"
            :value="isVaultMarker ? 'VAULT SIGNAL' : dwellers?.length ?? 0"
            compact
          />
        </div>
      </section>

      <section class="border-l-2 border-theme-primary/50 bg-surface p-4">
        <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">SITE NOTES</p>
        <p class="mt-2 text-sm leading-6 text-theme-primary/85">{{ description }}</p>
      </section>

      <section v-if="dwellers" class="border-t border-theme-primary/20 pt-4">
        <h4 class="mb-2 text-sm font-bold uppercase text-theme-primary">Linked Dwellers</h4>
        <ul class="space-y-1.5">
          <li v-for="d in dwellers" :key="d.dweller_id">
            <button type="button" class="dweller-entry flex w-full items-center justify-between gap-3 rounded border border-theme-primary/20 bg-surface px-3 py-2 text-left transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50" @click="goToDweller(d.dweller_id)">
              <span class="text-sm text-theme-primary underline underline-offset-2">{{ dwellerDisplayName(d.first_name, d.last_name) }}</span>
              <span class="text-xs text-theme-primary/60">{{ d.relation }}</span>
            </button>
          </li>
        </ul>
      </section>
    </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
