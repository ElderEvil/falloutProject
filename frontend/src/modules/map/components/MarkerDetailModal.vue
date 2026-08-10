<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import UModal from '@/core/components/ui/UModal.vue'
import UBadge from '@/core/components/ui/UBadge.vue'
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

const isLocked = computed(() => props.location !== null && !props.location.is_unlocked)

function goToDweller(dwellerId: string) {
  isOpen.value = false
  router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}

function dwellerDisplayName(first: string, last: string | null) {
  return last ? `${first} ${last}` : first
}
</script>

<template>
  <UModal v-model="isOpen" :title="placeName" size="lg">
    <div v-if="isLocked" class="locked-placeholder">
      <Icon icon="mdi:lock-question" class="locked-icon" />
      <h3 class="locked-heading">Unknown Location</h3>
      <p class="locked-description">
        Chat with a dweller who has been here to uncover this place.
      </p>
    </div>
    <div v-else class="marker-detail">
      <div class="detail-header">
        <UBadge :variant="badgeVariant" size="md">
          {{ placeType }}
        </UBadge>
      </div>

      <p class="detail-description">{{ description }}</p>

      <div v-if="dwellers" class="detail-dwellers">
        <h4 class="dwellers-heading">Linked Dwellers</h4>
        <ul class="dwellers-list">
          <li v-for="d in dwellers" :key="d.dweller_id">
            <button type="button" class="dweller-entry" @click="goToDweller(d.dweller_id)">
              <span class="dweller-name">{{ dwellerDisplayName(d.first_name, d.last_name) }}</span>
              <span class="dweller-relation">({{ d.relation }})</span>
            </button>
          </li>
        </ul>
      </div>
    </div>
  </UModal>
</template>

<style scoped>
.marker-detail {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.detail-description {
  color: var(--color-theme-primary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  opacity: 0.85;
}

.detail-dwellers {
  border-top: 1px solid var(--color-theme-glow);
  padding-top: 0.75rem;
}

.dwellers-heading {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-bold);
  color: var(--color-theme-primary);
  margin-bottom: 0.5rem;
}

.dwellers-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.dweller-entry {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.375rem 0.5rem;
  border: 1px solid transparent;
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  background: none;
  font: inherit;
  color: inherit;
  text-align: left;
}

.dweller-entry:hover,
.dweller-entry:focus-visible {
  border-color: var(--color-theme-primary);
  box-shadow: var(--shadow-glow-sm);
}

.dweller-entry:focus-visible {
  outline: none;
}

.dweller-name {
  color: var(--color-theme-primary);
  font-size: var(--font-size-sm);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.dweller-relation {
  color: var(--color-theme-primary);
  font-size: var(--font-size-xs);
  opacity: 0.6;
}

.locked-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 1.5rem 0;
}

.locked-icon {
  width: 4rem;
  height: 4rem;
  color: var(--color-theme-primary);
  opacity: 0.4;
}

.locked-heading {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--color-theme-primary);
  margin-top: 1rem;
}

.locked-description {
  color: var(--color-theme-primary);
  font-size: var(--font-size-sm);
  opacity: 0.6;
  margin-top: 0.5rem;
}
</style>
