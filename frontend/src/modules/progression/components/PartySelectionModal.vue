<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import UModal from '@/core/components/ui/UModal.vue'
import UButton from '@/core/components/ui/UButton.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { VaultQuest } from '../models/quest'

interface Props {
  modelValue: boolean
  quest: VaultQuest | null
  dwellers: DwellerShort[]
  currentParty: DwellerShort[]
  maxPartySize?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxPartySize: 3,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'assign', dwellerIds: string[]): void
  (e: 'start'): void
}>()

const selectedDwellerIds = ref<string[]>([])

// Sync with current party when modal opens
watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen) {
      selectedDwellerIds.value = props.currentParty.map((d) => d.id)
    }
  }
)

const canSubmit = computed(() => selectedDwellerIds.value.length > 0)

const availableDwellers = computed(() => {
  // Filter out dwellers already in other quests (excluding current quest's party)
  return props.dwellers.filter((dweller) => {
    // Include if already selected for this quest
    if (selectedDwellerIds.value.includes(dweller.id)) return true

    // Only show idle or working dwellers (not on other quests)
    // Note: In a real implementation, we'd check if they're on another quest
    return dweller.status === 'idle' || dweller.status === 'working'
  })
})

const selectedDwellers = computed(() => {
  return selectedDwellerIds.value
    .map((id) => props.dwellers.find((d) => d.id === id))
    .filter((d): d is DwellerShort => d !== undefined)
})

const toggleDweller = (dwellerId: string) => {
  const index = selectedDwellerIds.value.indexOf(dwellerId)
  if (index === -1) {
    // Add dweller if not at max
    if (selectedDwellerIds.value.length < props.maxPartySize) {
      selectedDwellerIds.value.push(dwellerId)
    }
  } else {
    // Remove dweller
    selectedDwellerIds.value.splice(index, 1)
  }
}

const isSelected = (dwellerId: string) => {
  return selectedDwellerIds.value.includes(dwellerId)
}

const getDwellerName = (dweller: DwellerShort) => {
  return `${dweller.first_name} ${dweller.last_name}`
}

const getDwellerLevel = (dweller: DwellerShort) => {
  return dweller.level || 1
}

const close = () => {
  emit('update:modelValue', false)
}

const handleAssign = () => {
  console.log('[PartySelectionModal] handleAssign, emitting assign with:', selectedDwellerIds.value)
  emit('assign', selectedDwellerIds.value)
}

const handleStart = () => {
  emit('start')
}
</script>

<template>
  <UModal
    :model-value="modelValue"
    :title="quest ? `Assign Party: ${quest.title}` : 'Assign Party'"
    size="lg"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="quest" class="party-modal-content">
      <!-- Party Slots -->
      <div class="party-slots">
        <div class="slots-label">
          <Icon icon="mdi:account-group" class="inline-icon" />
          Party Slots ({{ selectedDwellerIds.length }} / {{ maxPartySize }})
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
              <button class="slot-remove" @click="toggleDweller(selectedDwellers[slot - 1].id)">
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

      <!-- Available Dwellers -->
      <div class="available-dwellers">
        <div class="dwellers-label">
          <Icon icon="mdi:account-search" class="inline-icon" />
          Available Dwellers
        </div>
        <div class="dwellers-list">
          <div
            v-for="dweller in availableDwellers"
            :key="dweller.id"
            class="dweller-item"
            :class="{ selected: isSelected(dweller.id) }"
            @click="toggleDweller(dweller.id)"
          >
            <div class="dweller-checkbox">
              <Icon
                :icon="isSelected(dweller.id) ? 'mdi:checkbox-marked' : 'mdi:checkbox-blank-outline'"
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
              <UBadge :variant="dweller.status === 'idle' ? 'success' : 'warning'">
                {{ dweller.status }}
              </UBadge>
            </div>
          </div>

          <div v-if="availableDwellers.length === 0" class="no-dwellers">
            <Icon icon="mdi:account-off" class="no-dwellers-icon" />
            <p>No available dwellers found</p>
            <p class="hint">Build more living quarters to get more dwellers</p>
          </div>
        </div>
      </div>

      <!-- Quest Duration Info -->
      <div v-if="quest.duration_minutes" class="quest-duration">
        <Icon icon="mdi:clock-outline" class="inline-icon" />
        Estimated Duration: {{ quest.duration_minutes }} minutes
      </div>
    </div>

    <template #footer>
      <div class="modal-actions">
        <UButton variant="secondary" @click="close"> Cancel </UButton>
        <UButton variant="primary" :disabled="!canSubmit" @click="handleAssign">
          <Icon icon="mdi:check" class="btn-icon" />
          Assign Party
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.party-modal-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.party-slots {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  padding: 16px;
}

.slots-label,
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
  background: rgba(0, 255, 0, 0.05);
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
  color: #ff4444;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.slot-remove:hover {
  background: rgba(255, 68, 68, 0.2);
}

.available-dwellers {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  padding: 16px;
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
  background: rgba(0, 255, 0, 0.05);
  border-color: var(--color-theme-glow);
}

.dweller-item.selected {
  background: rgba(0, 255, 0, 0.1);
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

.quest-duration {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: rgba(0, 217, 255, 0.1);
  border: 1px solid var(--color-theme-accent);
  border-radius: 6px;
  color: var(--color-theme-accent);
  font-size: 0.9rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-icon {
  margin-right: 8px;
}
</style>
