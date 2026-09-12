<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import UModal from '@/core/components/ui/UModal.vue'
import UBadge from '@/core/components/ui/UBadge.vue'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '../models/map'

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

const vaultId = computed(() => route.params.id as string)

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
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'default'> = {
    home_vault: 'success',
    origin: 'info',
    visited: 'default',
    discovery: 'warning',
    vault: 'danger',
  }
  return map[placeType.value] ?? 'default'
})

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
  <UModal v-model="isOpen" :title="modalTitle" size="md" surface="base">
    <div v-if="isLocked" class="locked-location-view">
      <div class="locked-scanline-header" aria-hidden="true"></div>
      <div class="flex flex-col items-center py-6 text-center">
        <Icon icon="mdi:lock-question" class="locked-icon" />
        <h3 class="mt-4 text-lg font-bold text-theme-primary terminal-glow-subtle">Unknown Location</h3>
        <p class="mt-2 max-w-sm text-sm leading-6 text-theme-primary/60">
          Chat with a dweller who has been here to uncover this place.
        </p>
        <div v-if="dwellers" class="mt-4 w-full max-w-sm space-y-1.5 text-left">
          <p class="section-label">KNOWN CONTACTS</p>
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
    </div>
    <div v-else class="space-y-5">
      <section class="field-report-section">
        <div class="field-report-scanline" aria-hidden="true"></div>
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="section-label">WASTELAND FIELD REPORT</p>
            <p class="mt-1 text-sm font-bold text-theme-primary">{{ recordStatus }}</p>
          </div>
          <UBadge :variant="badgeVariant" size="md">{{ placeType }}</UBadge>
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

      <section class="site-notes-section">
        <p class="section-label">SITE NOTES</p>
        <p class="mt-2 text-sm leading-6 text-theme-primary/85">{{ description }}</p>
      </section>

      <section v-if="dwellers" class="border-t border-theme-primary/20 pt-4">
        <h4 class="mb-2 text-sm font-bold uppercase text-theme-primary">
          <span class="text-theme-primary/40">[</span>
          Linked Dwellers
          <span class="text-theme-primary/40">]</span>
        </h4>
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
  </UModal>
</template>

<style scoped>
.locked-location-view {
  position: relative;
  overflow: hidden;
}

.locked-scanline-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: repeating-linear-gradient(
    to right,
    var(--color-theme-primary) 0px,
    var(--color-theme-primary) 2px,
    transparent 2px,
    transparent 4px
  );
  opacity: 0.15;
}

.locked-icon {
  width: 4rem;
  height: 4rem;
  color: var(--color-theme-primary);
  opacity: 0.3;
  animation: locked-static 3s steps(3) infinite;
}

.field-report-section {
  position: relative;
  overflow: hidden;
  border-radius: 0.25rem;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  background-color: var(--color-surface-sunken);
  padding: 1rem;
}

.field-report-scanline {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--color-theme-primary);
  opacity: 0.1;
}

.site-notes-section {
  border-left: 2px solid color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
  background-color: var(--color-surface);
  padding: 1rem;
}

.section-label {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--color-theme-primary);
  opacity: 0.6;
}

@keyframes locked-static {
  0%, 100% { opacity: 0.3; }
  33% { opacity: 0.2; }
  66% { opacity: 0.35; }
}
</style>
