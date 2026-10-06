<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { getDwellerDisplayName, type DwellerShort } from '@/modules/dwellers/models/dweller'

interface Props {
  /** Candidate dwellers to render (already filtered/sorted by the caller). */
  dwellers: DwellerShort[]
  /** Ids currently selected in the party. */
  selectedIds: string[]
  /** Shows the eligibility spinner in place of the list. */
  isLoading: boolean
  /** Quest mode with at least one eligible dweller: show the "Level Requirements Met" badge. */
  showEligibleBadge: boolean
  /** Eligibility-fetch failure message; renders in place of the generic empty state. */
  error: string | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'toggle', dwellerId: string): void
}>()

const isSelected = (dwellerId: string) => props.selectedIds.includes(dwellerId)
const getDwellerName = (dweller: DwellerShort) => getDwellerDisplayName(dweller)
const getDwellerLevel = (dweller: DwellerShort) => dweller.level || 1
</script>

<template>
  <div class="available-dwellers">
    <div class="dwellers-label">
      <Icon icon="mdi:account-search" class="inline-icon" />
      Available Dwellers
      <span v-if="isLoading" class="loading-text">(Loading...)</span>
      <span v-else-if="showEligibleBadge" class="eligible-badge">(Level Requirements Met)</span>
    </div>
    <div v-if="isLoading" class="loading-dwellers">
      <Icon icon="mdi:loading" class="loading-icon spin" />
      <p>Checking dweller eligibility...</p>
    </div>
    <div v-else class="dwellers-list">
      <div
        v-for="dweller in dwellers"
        :key="dweller.id"
        class="dweller-item"
        :class="{ selected: isSelected(dweller.id) }"
        @click="emit('toggle', dweller.id)"
      >
        <div class="dweller-checkbox">
          <Icon
            :icon="
              isSelected(dweller.id) ? 'mdi:checkbox-marked' : 'mdi:checkbox-blank-outline'
            "
            class="checkbox-icon"
          />
        </div>
        <div class="dweller-avatar">
          <Icon icon="mdi:account" class="avatar-icon" />
        </div>
        <div class="dweller-info">
          <span class="dweller-name">{{ getDwellerName(dweller) }}</span>
          <span class="dweller-stats">Level {{ getDwellerLevel(dweller) }}</span>
        </div>
        <div class="dweller-status">
          <Badge
            variant="default"
            :class="dweller.status === 'idle' ? '' : 'border-warning bg-warning/10 text-warning'"
          >
            {{ dweller.status === 'resting' ? 'Socializing' : dweller.status }}
          </Badge>
        </div>
      </div>

      <div v-if="dwellers.length === 0" class="no-dwellers">
        <Icon icon="mdi:account-off" class="no-dwellers-icon" />
        <p v-if="error">{{ error }}</p>
        <p v-else>No available dwellers found</p>
        <p v-if="!error" class="hint">Build more living quarters to get more dwellers</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.available-dwellers {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  padding: 16px;
}

.dwellers-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  font-weight: bold;
  color: var(--color-theme-accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 12px;
}

.inline-icon {
  font-size: 1.2rem;
}

.dwellers-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dweller-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.dweller-item:hover {
  background: rgba(var(--color-theme-primary-rgb), 0.05);
  border-color: var(--color-theme-glow);
}

.dweller-item.selected {
  background: rgba(var(--color-theme-primary-rgb), 0.1);
  border-color: var(--color-theme-accent);
}

.dweller-checkbox {
  color: var(--color-theme-primary);
}

.checkbox-icon {
  font-size: 1.3rem;
}

.dweller-item.selected .checkbox-icon {
  color: var(--color-theme-accent);
}

.dweller-avatar {
  background: rgba(0, 0, 0, 0.4);
  border-radius: 50%;
  padding: 8px;
}

.avatar-icon {
  font-size: 1.5rem;
  color: var(--color-theme-primary);
}

.dweller-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.dweller-name {
  font-weight: bold;
  color: var(--color-theme-primary);
}

.dweller-stats {
  font-size: 0.8rem;
  color: var(--color-theme-accent);
}

.dweller-status {
  flex-shrink: 0;
}

.no-dwellers {
  text-align: center;
  padding: 40px 20px;
  color: var(--color-theme-primary);
  opacity: 0.6;
}

.no-dwellers-icon {
  font-size: 3rem;
  margin-bottom: 16px;
}

.hint {
  font-size: 0.85rem;
  margin-top: 8px;
  opacity: 0.7;
}

.loading-text {
  font-size: 0.8rem;
  color: var(--color-theme-accent);
  font-weight: normal;
}

.eligible-badge {
  font-size: 0.8rem;
  color: var(--color-theme-primary);
  font-weight: normal;
}

.loading-dwellers {
  text-align: center;
  padding: 40px 20px;
  color: var(--color-theme-primary);
}

.loading-icon {
  font-size: 2rem;
  margin-bottom: 12px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
