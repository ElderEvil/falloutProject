<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { getDwellerDisplayName, type DwellerShort } from '@/modules/dwellers/models/dweller'

interface Props {
  /** Selected dwellers in slot order; missing slots render empty. */
  selectedDwellers: DwellerShort[]
  /** Raw selected count for the header — may exceed resolvable dwellers. */
  selectedCount: number
  maxPartySize: number
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'remove', dwellerId: string): void
}>()

const getDwellerName = (dweller: DwellerShort) => getDwellerDisplayName(dweller)
const getDwellerLevel = (dweller: DwellerShort) => dweller.level || 1
</script>

<template>
  <div class="party-slots">
    <div class="slots-label">
      <Icon icon="mdi:account-group" class="inline-icon" />
      Party Slots ({{ selectedCount }} / {{ maxPartySize }})
    </div>
    <div class="slots-grid">
      <div
        v-for="slot in maxPartySize"
        :key="slot"
        class="party-slot"
        :class="{ filled: selectedDwellers[slot - 1] }"
      >
        <div v-if="selectedDwellers[slot - 1]" class="slot-dweller">
          <Icon icon="mdi:account" class="slot-icon" />
          <div class="slot-info">
            <span class="slot-name">{{ getDwellerName(selectedDwellers[slot - 1]) }}</span>
            <span class="slot-level">Lv. {{ getDwellerLevel(selectedDwellers[slot - 1]) }}</span>
          </div>
          <button
            type="button"
            class="slot-remove"
            :aria-label="`Remove ${getDwellerName(selectedDwellers[slot - 1])} from party`"
            @click="emit('remove', selectedDwellers[slot - 1].id)"
          >
            <Icon icon="mdi:close" />
          </button>
        </div>
        <div v-else class="slot-empty">
          <Icon icon="mdi:account-plus" class="slot-icon" />
          <span>Empty Slot</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.party-slots {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  padding: 16px;
}

.slots-label {
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

.slots-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.party-slot {
  background: rgba(0, 0, 0, 0.4);
  border: 2px dashed var(--color-theme-primary);
  border-radius: 8px;
  padding: 16px;
  min-height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.party-slot.filled {
  border-style: solid;
  border-color: var(--color-theme-accent);
  background: rgba(var(--color-theme-primary-rgb), 0.05);
}

.slot-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.slot-icon {
  font-size: 2rem;
}

.slot-dweller {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.slot-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.slot-name {
  font-weight: bold;
  font-size: 0.85rem;
  color: var(--color-theme-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.slot-level {
  font-size: 0.75rem;
  color: var(--color-theme-accent);
}

.slot-remove {
  background: none;
  border: none;
  color: var(--color-danger);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.slot-remove:hover {
  background: rgba(255, 68, 68, 0.2);
}
</style>
