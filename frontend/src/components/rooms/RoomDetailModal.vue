<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import type { Room } from '@/models/room'
import type { DwellerShort } from '@/models/dweller'
import { useDwellerStore } from '@/stores/dweller'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import UModal from '@/components/ui/UModal.vue'
import UButton from '@/components/ui/UButton.vue'

interface Props {
  room: Room | null
  modelValue: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  close: []
  roomUpdated: []
}>()

const route = useRoute()
const router = useRouter()
const dwellerStore = useDwellerStore()
const roomStore = useRoomStore()
const authStore = useAuthStore()

const isUpgrading = ref(false)
const isDestroying = ref(false)
const isRushing = ref(false)
const actionError = ref<string | null>(null)

// Get dwellers assigned to this room
const assignedDwellers = computed<DwellerShort[]>(() => {
  if (!props.room) return []
  return dwellerStore.dwellers.filter((d) => d.room_id === props.room!.id)
})

// Calculate dweller capacity based on room size
// Base capacity: 2 dwellers per room
// Each merge adds 2 more dwellers (max 3 merges = 6 dwellers total)
const dwellerCapacity = computed(() => {
  if (!props.room) return 0
  const room = props.room
  const roomSize = room.size || room.size_min || 3
  const cellsOccupied = Math.ceil(roomSize / 3)
  return cellsOccupied * 2
})

// Get resource icon based on room ability
const resourceIcon = computed(() => {
  if (!props.room?.ability) return 'mdi:home'
  const ability = props.room.ability.toUpperCase()
  switch (ability) {
    case 'STRENGTH': return 'mdi:lightning-bolt'
    case 'PERCEPTION': return 'mdi:water'
    case 'AGILITY': return 'mdi:food-drumstick'
    case 'ENDURANCE': return 'mdi:flash'
    default: return 'mdi:home'
  }
})

// Get resource name
const resourceName = computed(() => {
  if (!props.room?.ability) return 'Resources'
  const ability = props.room.ability.toUpperCase()
  switch (ability) {
    case 'STRENGTH': return 'Power'
    case 'PERCEPTION': return 'Water'
    case 'AGILITY': return 'Food'
    case 'ENDURANCE': return 'All Resources'
    default: return 'Resources'
  }
})

// Room status (static for now, will be dynamic later)
const roomStatus = computed(() => 'Operational')

// Calculate production rate based on dwellers and room stats
const productionInfo = computed(() => {
  if (!props.room || !props.room.ability || props.room.category !== 'PRODUCTION') {
    return null
  }

  const room = props.room
  const dwellers = assignedDwellers.value

  // Calculate ability sum (sum of relevant SPECIAL stat)
  const abilityKey = room.ability.toLowerCase() as 'strength' | 'perception' | 'endurance' | 'charisma' | 'intelligence' | 'agility' | 'luck'
  const abilitySum = dwellers.reduce((sum, dweller) => {
    const value = dweller[abilityKey]
    return sum + (typeof value === 'number' ? value : 0)
  }, 0)

  // Production calculation matching backend logic
  const BASE_PRODUCTION_RATE = 0.1
  const TIER_MULTIPLIER: Record<number, number> = { 1: 1.0, 2: 1.5, 3: 2.0 }
  const tierMult = TIER_MULTIPLIER[room.tier] || 1.0
  const productionPerSecond = (room.output || 0) * abilitySum * BASE_PRODUCTION_RATE * tierMult
  const productionPerMinute = productionPerSecond * 60

  // Determine resource type
  let resourceType = 'Unknown'
  const abilityUpper = room.ability.toUpperCase()
  switch (abilityUpper) {
    case 'STRENGTH':
      resourceType = 'Power'
      break
    case 'AGILITY':
      resourceType = 'Food'
      break
    case 'PERCEPTION':
      resourceType = 'Water'
      break
    case 'ENDURANCE':
      resourceType = 'All Resources'
      break
  }

  // Calculate efficiency (percentage of dweller capacity filled)
  const capacity = dwellerCapacity.value || 1
  const efficiency = Math.round((dwellers.length / capacity) * 100)

  return {
    resourceType,
    abilitySum,
    productionPerMinute: productionPerMinute.toFixed(2),
    productionPerSecond: productionPerSecond.toFixed(2),
    efficiency,
    isFullyStaffed: dwellers.length >= capacity
  }
})

// Room upgrade info
const upgradeInfo = computed(() => {
  if (!props.room) return null

  const room = props.room
  const maxTier = room.t2_upgrade_cost && room.t3_upgrade_cost ? 3 : room.t2_upgrade_cost ? 2 : 1
  const canUpgrade = room.tier < maxTier

  let upgradeCost = 0
  if (room.tier === 1 && room.t2_upgrade_cost) {
    upgradeCost = room.t2_upgrade_cost
  } else if (room.tier === 2 && room.t3_upgrade_cost) {
    upgradeCost = room.t3_upgrade_cost
  }

  return {
    canUpgrade,
    upgradeCost,
    nextTier: room.tier + 1,
    maxTier
  }
})

// Handle upgrade
const handleUpgrade = async () => {
  if (!props.room) return

  const vaultId = route.params.id as string
  if (!vaultId) {
    actionError.value = 'No vault ID available'
    return
  }

  isUpgrading.value = true
  actionError.value = null

  try {
    await roomStore.upgradeRoom(props.room.id, authStore.token as string, vaultId)
    emit('roomUpdated')
    emit('close')
  } catch (error) {
    console.error('Failed to upgrade room:', error)
    actionError.value = error instanceof Error ? error.message : 'Failed to upgrade room'
  } finally {
    isUpgrading.value = false
  }
}

// Handle destroy
const handleDestroy = async () => {
  if (!props.room) return

  if (!confirm(`Are you sure you want to destroy ${props.room.name}? You will receive a partial refund.`)) {
    return
  }

  isDestroying.value = true
  actionError.value = null

  try {
    await roomStore.destroyRoom(props.room.id, authStore.token as string)
    emit('roomUpdated')
    emit('close')
  } catch (error) {
    console.error('Failed to destroy room:', error)
    actionError.value = error instanceof Error ? error.message : 'Failed to destroy room'
  } finally {
    isDestroying.value = false
  }
}

// Handle unassign all dwellers
const handleUnassignAll = async () => {
  if (!props.room || assignedDwellers.value.length === 0) return

  if (!confirm(`Unassign all ${assignedDwellers.value.length} dwellers from this room?`)) {
    return
  }

  actionError.value = null

  try {
    // Unassign each dweller (set room_id to null)
    for (const dweller of assignedDwellers.value) {
      await dwellerStore.assignDwellerToRoom(dweller.id, null, authStore.token as string)
    }
    emit('roomUpdated')
  } catch (error) {
    console.error('Failed to unassign dwellers:', error)
    actionError.value = error instanceof Error ? error.message : 'Failed to unassign dwellers'
  }
}

// Get SPECIAL stat label for the room's ability
const getAbilityLabel = (ability: string) => {
  const labels: Record<string, string> = {
    STRENGTH: 'S - Strength',
    PERCEPTION: 'P - Perception',
    ENDURANCE: 'E - Endurance',
    CHARISMA: 'C - Charisma',
    INTELLIGENCE: 'I - Intelligence',
    AGILITY: 'A - Agility',
    LUCK: 'L - Luck'
  }
  return labels[ability.toUpperCase()] || ability
}

// Get dweller's relevant SPECIAL stat value
const getDwellerStatValue = (dweller: DwellerShort, ability: string) => {
  const key = ability.toLowerCase() as 'strength' | 'perception' | 'endurance' | 'charisma' | 'intelligence' | 'agility' | 'luck'
  const value = dweller[key]
  return typeof value === 'number' ? value : 0
}

// Handle rush production (placeholder for future implementation)
const handleRushProduction = async () => {
  if (!props.room) return

  // TODO: Implement rush production logic
  // - Calculate rush cost (caps)
  // - Calculate incident probability
  // - Show confirmation dialog with risk percentage
  // - Call API endpoint to rush production
  // - Handle success/failure with loot or incident

  actionError.value = 'Rush Production feature coming soon!'
  setTimeout(() => {
    actionError.value = null
  }, 3000)
}

// Handle opening dweller details
const openDwellerDetails = (dwellerId: string) => {
  // Navigate to dweller detail page
  const vaultId = route.params.id as string
  if (vaultId) {
    router.push({
      name: 'dwellerDetail',
      params: { id: vaultId, dwellerId }
    })
  }
}

// Clear error when modal closes
watch(() => props.modelValue, (newValue) => {
  if (!newValue) {
    actionError.value = null
  }
})
</script>

<template>
  <UModal :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" @close="emit('close')" size="lg">
    <template #header>
      <div class="modal-header">
        <div class="header-content">
          <h2 class="room-title">
            <Icon :icon="resourceIcon" class="room-icon" />
            {{ room?.name }}
          </h2>
          <div class="header-metadata">
            <span class="metadata-item">{{ room?.category }} Room</span>
            <span class="metadata-divider">·</span>
            <span class="metadata-item">Tier {{ room?.tier }}</span>
            <span v-if="room?.ability" class="metadata-divider">·</span>
            <span v-if="room?.ability" class="metadata-item">Requires: {{ room.ability.charAt(0) }}</span>
          </div>
        </div>
      </div>
    </template>

    <div v-if="room" class="modal-content">
      <!-- Error display -->
      <div v-if="actionError" class="error-banner">
        <Icon icon="mdi:alert-circle" class="h-5 w-5" />
        {{ actionError }}
      </div>

      <!-- Room Visual Preview Section -->
      <!-- TODO: This section will render room sprite and dweller sprites in the future -->
      <div class="section room-preview-section">
        <h3 class="section-title">
          <Icon icon="mdi:image-outline" class="h-5 w-5" />
          Room Preview
        </h3>
        <div class="preview-container">
          <!-- Room Image Placeholder with Dwellers Inside -->
          <div class="room-image-placeholder">
            <Icon icon="mdi:home-variant-outline" class="h-16 w-16 opacity-30" />
            <p class="placeholder-text">Room Sprite</p>
            <p class="placeholder-subtext">Coming Soon</p>

            <!-- Dweller Sprites Container - Positioned Over Room -->
            <div class="dweller-sprites-overlay">
              <div
                v-for="slot in dwellerCapacity"
                :key="`slot-${slot}`"
                class="dweller-sprite-slot"
                :class="{ 'slot-filled': assignedDwellers[slot - 1] }"
              >
                <template v-if="assignedDwellers[slot - 1]">
                  <div class="placeholder-dweller">
                    <span class="dweller-initial">{{ assignedDwellers[slot - 1].first_name[0] }}</span>
                  </div>
                </template>
                <template v-else>
                  <div class="placeholder-dweller empty">
                    <Icon icon="mdi:account-outline" class="h-6 w-6 opacity-30" />
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Room Info Section -->
      <div class="section">
        <h3 class="section-title">
          <Icon icon="mdi:information" class="h-5 w-5" />
          Room Information
        </h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">Dwellers:</span>
            <span class="info-value">{{ assignedDwellers.length }} / {{ dwellerCapacity }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Resource Capacity:</span>
            <span class="info-value">{{ room.capacity || 0 }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Room Size:</span>
            <span class="info-value">{{ Math.ceil((room.size || room.size_min) / 3) }}x merged</span>
          </div>
          <div class="info-item">
            <span class="info-label">Position:</span>
            <span class="info-value">({{ room.coordinate_x }}, {{ room.coordinate_y }})</span>
          </div>
          <div v-if="room.ability" class="info-item">
            <span class="info-label">Required Stat:</span>
            <span class="info-value">{{ getAbilityLabel(room.ability) }}</span>
          </div>
        </div>
      </div>

      <!-- Production Stats (for production rooms) -->
      <div v-if="productionInfo" class="section">
        <h3 class="section-title">
          <Icon icon="mdi:chart-line" class="h-5 w-5" />
          Production Statistics
        </h3>
        <div class="production-stats">
          <div class="stat-card">
            <div class="stat-label">Resource Type</div>
            <div class="stat-value">{{ productionInfo.resourceType }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Production Rate</div>
            <div class="stat-value">{{ productionInfo.productionPerMinute }} /min</div>
            <div class="stat-subvalue">{{ productionInfo.productionPerSecond }} /sec</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Efficiency</div>
            <div class="stat-value" :class="{ 'text-success': productionInfo.isFullyStaffed }">
              {{ productionInfo.efficiency }}%
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Total Stat Points</div>
            <div class="stat-value">{{ productionInfo.abilitySum }}</div>
          </div>
        </div>
      </div>

      <!-- Assigned Dwellers Section - Detailed List -->
      <div class="section dweller-section">
        <h3 class="section-title dweller-section-title">
          <Icon icon="mdi:account-group" class="h-5 w-5" />
          Dweller Details ({{ assignedDwellers.length }})
        </h3>
        <div v-if="assignedDwellers.length > 0" class="dwellers-list">
          <div
            v-for="dweller in assignedDwellers"
            :key="dweller.id"
            class="dweller-card clickable"
            @click="openDwellerDetails(dweller.id)"
          >
            <div class="dweller-info">
              <div class="dweller-name">{{ dweller.first_name }} {{ dweller.last_name }}</div>
              <div class="dweller-level">Level {{ dweller.level }}</div>
            </div>
            <div v-if="room.ability" class="dweller-stat">
              <span class="stat-label">{{ room.ability.charAt(0) }}</span>
              <span class="stat-value">{{ getDwellerStatValue(dweller, room.ability) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <Icon icon="mdi:account-off" class="h-12 w-12 opacity-50" />
          <p>No dwellers assigned to this room</p>
          <p class="text-sm">Drag dwellers from the sidebar to assign them</p>
        </div>
      </div>

      <!-- Management Actions Section -->
      <div class="section">
        <h3 class="section-title">
          <Icon icon="mdi:cog" class="h-5 w-5" />
          Management
        </h3>
        <div class="actions-grid">
          <!-- Upgrade Button -->
          <UButton
            v-if="upgradeInfo?.canUpgrade"
            @click="handleUpgrade"
            :disabled="isUpgrading"
            variant="primary"
            class="action-btn"
          >
            <Icon icon="mdi:arrow-up-circle" class="h-5 w-5" />
            <span>Upgrade to Tier {{ upgradeInfo.nextTier }}</span>
            <span class="cost-badge">{{ upgradeInfo.upgradeCost }} caps</span>
          </UButton>
          <div v-else class="disabled-action">
            <Icon icon="mdi:arrow-up-circle" class="h-5 w-5 opacity-50" />
            <span>Max tier reached ({{ room.tier }}/{{ upgradeInfo?.maxTier }})</span>
          </div>

          <!-- Rush Production Button (Placeholder) -->
          <UButton
            v-if="productionInfo"
            @click="handleRushProduction"
            :disabled="isRushing || assignedDwellers.length === 0"
            variant="primary"
            class="action-btn rush-btn"
          >
            <Icon icon="mdi:lightning-bolt" class="h-5 w-5" />
            <span>Rush Production</span>
            <span class="feature-badge">Coming Soon</span>
          </UButton>

          <!-- Unassign All Button -->
          <UButton
            @click="handleUnassignAll"
            :disabled="assignedDwellers.length === 0"
            variant="secondary"
            class="action-btn"
          >
            <Icon icon="mdi:account-remove" class="h-5 w-5" />
            <span>Unassign All Dwellers</span>
          </UButton>

          <!-- Destroy Button -->
          <UButton
            @click="handleDestroy"
            :disabled="isDestroying"
            variant="danger"
            class="action-btn"
          >
            <Icon icon="mdi:delete" class="h-5 w-5" />
            <span>Destroy Room</span>
          </UButton>
        </div>
      </div>
    </div>
  </UModal>
</template>

<style scoped>
.modal-header {
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(0, 255, 0, 0.3);
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.room-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.25rem;
  font-weight: bold;
  color: #00ff00;
  margin: 0;
}

.room-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-terminal-green);
  filter: drop-shadow(0 0 4px rgba(0, 255, 0, 0.5));
}

.header-metadata {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metadata-item {
  color: #888;
}

.metadata-divider {
  color: #555;
}

.close-btn {
  background: none;
  border: none;
  color: #00ff00;
  cursor: pointer;
  padding: 0.5rem;
  transition: all 0.2s;
}

.close-btn:hover {
  color: #00ff00;
  transform: scale(1.1);
}

.modal-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1rem 0;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(255, 0, 0, 0.1);
  border: 1px solid #ff0000;
  border-radius: 4px;
  color: #ff0000;
  font-size: 0.875rem;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.125rem;
  font-weight: 600;
  color: #00ff00;
  margin: 0;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: rgba(0, 255, 0, 0.05);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 4px;
}

.info-label {
  color: #aaa;
  font-size: 0.875rem;
  flex-shrink: 0;
}

.info-value {
  color: #00ff00;
  font-weight: 600;
  text-align: right;
}

.production-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
}

.stat-card {
  padding: 1rem;
  background: rgba(0, 255, 0, 0.05);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 4px;
  text-align: center;
}

.stat-label {
  font-size: 0.75rem;
  color: #aaa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #00ff00;
  margin-top: 0.5rem;
}

.stat-subvalue {
  font-size: 0.75rem;
  color: #888;
  margin-top: 0.25rem;
}

.text-success {
  color: #00ff00 !important;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
}

.dweller-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(0, 255, 0, 0.2);
}

.dweller-section-title {
  font-weight: 700;
}

.dwellers-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
}

.dweller-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: rgba(0, 255, 0, 0.05);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 4px;
  transition: all 0.2s;
}

.dweller-card.clickable {
  cursor: pointer;
}

.dweller-card.clickable:hover {
  background: rgba(0, 255, 0, 0.15);
  border-color: rgba(0, 255, 0, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 255, 0, 0.2);
}

.dweller-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.dweller-name {
  font-weight: 600;
  color: #00ff00;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dweller-level {
  font-size: 0.75rem;
  color: #aaa;
}

.dweller-stat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  flex-shrink: 0;
  min-width: 60px;
}

.dweller-stat .stat-label {
  font-weight: bold;
  color: #fbbf24;
  font-size: 0.875rem;
}

.dweller-stat .stat-value {
  font-size: 1.125rem;
  font-weight: bold;
  color: #00ff00;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: #888;
  text-align: center;
}

.empty-state p {
  margin: 0.5rem 0;
}

.actions-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  padding: 1rem 0;
}

.action-btn {
  flex: 0 1 auto;
  min-width: 200px;
}

.action-btn :deep(button) {
  justify-content: flex-start;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.cost-badge {
  margin-left: auto;
  padding: 0.25rem 0.75rem;
  background: #000;
  border: 2px solid #fbbf24;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: bold;
  color: #fbbf24;
  text-shadow: 0 0 8px rgba(251, 191, 36, 0.8);
}

.feature-badge {
  margin-left: auto;
  padding: 0.25rem 0.75rem;
  background: rgba(139, 92, 246, 0.3);
  border: 2px solid #8b5cf6;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
  color: #a78bfa;
  text-shadow: 0 0 4px rgba(139, 92, 246, 0.5);
  font-style: italic;
}

.rush-btn {
  position: relative;
  overflow: hidden;
}

.rush-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
  animation: shimmer 3s infinite;
}

@keyframes shimmer {
  0% {
    left: -100%;
  }
  100% {
    left: 100%;
  }
}

.disabled-action {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(128, 128, 128, 0.1);
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  color: #888;
  font-size: 0.875rem;
}

/* Room Preview Section Styles */
.room-preview-section {
  background: rgba(0, 255, 0, 0.02);
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid rgba(0, 255, 0, 0.1);
}

.preview-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.room-image-placeholder {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 150px;
  background: rgba(0, 0, 0, 0.3);
  border: 2px dashed rgba(0, 255, 0, 0.3);
  border-radius: 8px;
  padding: 1.25rem;
  animation: pulse-border 3s ease-in-out infinite;
}

@keyframes pulse-border {
  0%, 100% {
    border-color: rgba(0, 255, 0, 0.3);
  }
  50% {
    border-color: rgba(0, 255, 0, 0.5);
  }
}

.placeholder-text {
  margin: 1rem 0 0.25rem;
  font-size: 1.125rem;
  font-weight: 600;
  color: #00ff00;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.placeholder-subtext {
  font-size: 0.875rem;
  color: #888;
  font-style: italic;
}

.dweller-sprites-overlay {
  position: absolute;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 0.75rem;
  z-index: 10;
}

.dweller-sprite-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.placeholder-dweller {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 255, 0, 0.1);
  border: 2px dashed rgba(0, 255, 0, 0.3);
  border-radius: 8px;
  transition: all 0.3s;
}

.placeholder-dweller.empty {
  background: rgba(128, 128, 128, 0.05);
  border-color: rgba(128, 128, 128, 0.2);
}

.slot-filled .placeholder-dweller {
  background: rgba(0, 255, 0, 0.2);
  border: 2px solid rgba(0, 255, 0, 0.5);
  animation: glow-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%, 100% {
    box-shadow: 0 0 8px rgba(0, 255, 0, 0.3);
  }
  50% {
    box-shadow: 0 0 16px rgba(0, 255, 0, 0.6);
  }
}

.dweller-initial {
  font-size: 1.5rem;
  font-weight: bold;
  color: #00ff00;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
}

.dweller-slot-name {
  font-size: 0.75rem;
  font-weight: 500;
  color: #00ff00;
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dweller-slot-name.empty {
  color: #666;
  font-style: italic;
}
</style>
