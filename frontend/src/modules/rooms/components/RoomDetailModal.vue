<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useRoomStore } from '../stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { useVaultStore } from '@/modules/vault/stores/vault'
import axios from '@/core/plugins/axios'
import UModal from '@/core/components/ui/UModal.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import UAlert from '@/core/components/ui/UAlert.vue'

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
const vaultStore = useVaultStore()
const toast = useToast()

const isUpgrading = ref(false)
const isDestroying = ref(false)
const isRushing = ref(false)
const isRecruiting = ref(false)
const actionError = ref<string | null>(null)
const justUpgraded = ref(false)

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
    case 'STRENGTH':
      return 'mdi:lightning-bolt'
    case 'PERCEPTION':
      return 'mdi:water'
    case 'AGILITY':
      return 'mdi:food-drumstick'
    case 'ENDURANCE':
      return 'mdi:flash'
    default:
      return 'mdi:home'
  }
})

// Get resource name
const resourceName = computed(() => {
  if (!props.room?.ability) return 'Resources'
  const ability = props.room.ability.toUpperCase()
  switch (ability) {
    case 'STRENGTH':
      return 'Power'
    case 'PERCEPTION':
      return 'Water'
    case 'AGILITY':
      return 'Food'
    case 'ENDURANCE':
      return 'All Resources'
    default:
      return 'Resources'
  }
})

// Room status (static for now, will be dynamic later)
const roomStatus = computed(() => 'Operational')

// Room image URL with API base URL prepended
const roomImageUrl = computed(() => {
  if (!props.room?.image_url) return null
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  return `${baseUrl}${props.room.image_url}`
})

// Calculate production rate based on dwellers and room stats
const productionInfo = computed(() => {
  if (!props.room || !props.room.ability || props.room.category?.toLowerCase() !== 'production') {
    return null
  }

  const room = props.room
  const dwellers = assignedDwellers.value

  // Calculate ability sum (sum of relevant SPECIAL stat)
  const abilityKey = room.ability!.toLowerCase() as
    | 'strength'
    | 'perception'
    | 'endurance'
    | 'charisma'
    | 'intelligence'
    | 'agility'
    | 'luck'
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
  const abilityUpper = room.ability!.toUpperCase()
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
    isFullyStaffed: dwellers.length >= capacity,
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
    maxTier,
  }
})

// Check if room is Vault Door
const isVaultDoor = computed(() => {
  return props.room?.name?.toLowerCase() === 'vault door'
})

// Handle upgrade

const handleUpgrade = async () => {
  if (!props.room) return

  const vaultId = route.params.id as string
  if (!vaultId) {
    actionError.value = 'No vault ID available'
    return
  }

  const roomName = props.room.name
  const currentTier = props.room.tier
  const nextTier = currentTier + 1
  const upgradeCost = upgradeInfo.value?.upgradeCost || 0

  isUpgrading.value = true
  actionError.value = null

  try {
    await roomStore.upgradeRoom(props.room.id, authStore.token as string, vaultId)

    // Show success toast with upgrade details
    toast.success(`${roomName} upgraded to Tier ${nextTier}! (Cost: ${upgradeCost} caps)`, 5000)

    // Trigger visual feedback animation
    justUpgraded.value = true
    setTimeout(() => {
      justUpgraded.value = false
    }, 1000)

    emit('roomUpdated')
    // Don't close immediately - let user see the upgraded state
    setTimeout(() => {
      emit('close')
    }, 800)
  } catch (error) {
    console.error('Failed to upgrade room:', error)
    actionError.value = error instanceof Error ? error.message : 'Failed to upgrade room'
    toast.error(error instanceof Error ? error.message : 'Failed to upgrade room', 5000)
  } finally {
    isUpgrading.value = false
  }
}

// Handle destroy
const handleDestroy = async () => {
  if (!props.room) return

  if (
    !confirm(
      `Are you sure you want to destroy ${props.room.name}? You will receive a partial refund.`
    )
  ) {
    return
  }

  isDestroying.value = true
  actionError.value = null

  const vaultId = route.params.id as string
  if (!vaultId) {
    actionError.value = 'No vault ID available'
    isDestroying.value = false
    return
  }

  try {
    await roomStore.destroyRoom(props.room.id, authStore.token as string, vaultId)
    toast.success(`${props.room.name} destroyed. Caps refunded (50%).`)
    emit('roomUpdated')
    emit('close')
  } catch (error) {
    console.error('Failed to destroy room:', error)
    actionError.value = error instanceof Error ? error.message : 'Failed to destroy room'
    toast.error(error instanceof Error ? error.message : 'Failed to destroy room', 5000)
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
      await dwellerStore.unassignDwellerFromRoom(dweller.id, authStore.token as string)
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
    LUCK: 'L - Luck',
  }
  return labels[ability.toUpperCase()] || ability
}

// Get dweller's relevant SPECIAL stat value
const getDwellerStatValue = (dweller: DwellerShort, ability: string) => {
  const key = ability.toLowerCase() as
    | 'strength'
    | 'perception'
    | 'endurance'
    | 'charisma'
    | 'intelligence'
    | 'agility'
    | 'luck'
  const value = dweller[key]
  return typeof value === 'number' ? value : 0
}

// Radio Studio computed properties
const isRadioRoom = computed(() => {
  return props.room?.name.toLowerCase().includes('radio') || false
})

const localRadioMode = ref(vaultStore.activeVault?.radio_mode || 'recruitment')

watch(
  () => vaultStore.activeVault?.radio_mode,
  (newMode) => {
    if (newMode) {
      localRadioMode.value = newMode
    }
  }
)

const vaultId = computed(() => {
  return route.params.id as string
})

const manualRecruitCost = ref<number>(100)

// Fetch radio stats to get actual recruitment cost
const loadRadioStats = async () => {
  if (!vaultId.value || !isRadioRoom.value) return

  try {
    const response = await axios.get(`/api/v1/radio/vault/${vaultId.value}/stats`, {
      headers: { Authorization: `Bearer ${authStore.token}` }
    })
    if (response.data?.manual_cost_caps) {
      manualRecruitCost.value = response.data.manual_cost_caps
    }
  } catch (error) {
    console.error('Failed to load radio stats:', error)
  }
}

watch(() => props.modelValue, (newValue) => {
  if (newValue && isRadioRoom.value) {
    loadRadioStats()
  }
})

// Radio Studio handlers
const handleSwitchRadioMode = async (mode: 'recruitment' | 'happiness') => {
  if (!vaultId.value) return

  // Optimistic update
  localRadioMode.value = mode

  try {
    await axios.put(
      `/api/v1/radio/vault/${vaultId.value}/mode?mode=${mode}`,
      {},
      {
        headers: { Authorization: `Bearer ${authStore.token}` },
      }
    )

    // Refresh vault to get updated mode
    await vaultStore.refreshVault(vaultId.value, authStore.token!)

    toast.success(`Radio mode set to ${mode}`)
  } catch (error) {
    // Revert optimistically updated value on error
    localRadioMode.value =
      (vaultStore.activeVault?.radio_mode as 'recruitment' | 'happiness') || 'recruitment'
    console.error('Failed to switch radio mode:', error)
    toast.error('Failed to switch radio mode')
  }
}

const handleRecruitDweller = async () => {
  if (!vaultId.value) return

  if (localRadioMode.value !== 'recruitment') {
    toast.error('Radio must be in Recruitment mode')
    return
  }

  isRecruiting.value = true
  try {
    const response = await axios.post(
      `/api/v1/radio/vault/${vaultId.value}/recruit`,
      {},
      { headers: { Authorization: `Bearer ${authStore.token}` } }
    )

    toast.success(response.data.message || 'Dweller recruited successfully!')

    await vaultStore.refreshVault(vaultId.value, authStore.token!)
    await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token!)
  } catch (error: any) {
    console.error('Failed to recruit dweller:', error)
    const message = error.response?.data?.detail || 'Failed to recruit dweller'
    toast.error(message)
  } finally {
    isRecruiting.value = false
  }
}

// Handle rush production (placeholder for future implementation)
const handleRushProduction = async () => {
  if (!props.room) return

  // TODO (v1.14): Implement rush production logic
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
      params: { id: vaultId, dwellerId },
    })
  }
}

// Clear error when modal closes
watch(
  () => props.modelValue,
  (newValue) => {
    if (!newValue) {
      actionError.value = null
    }
  }
)

// Debug logging for room images (dev only)
watch(
  () => props.room,
  (newRoom) => {
    if (import.meta.env.DEV && newRoom) {
      console.log('🖼️ Room Detail Modal - Room loaded:', {
        name: newRoom.name,
        tier: newRoom.tier,
        size: newRoom.size,
        image_url: newRoom.image_url,
        has_image: !!newRoom.image_url,
      })
    }
  },
  { immediate: true }
)
</script>

<template>
  <UModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    @close="emit('close')"
    size="lg"
  >
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
            <span class="metadata-item" :class="{ 'tier-upgraded': justUpgraded }"
              >Tier {{ room?.tier }}</span
            >
            <span v-if="room?.ability" class="metadata-divider">·</span>
            <span v-if="room?.ability" class="metadata-item"
              >Requires: {{ room.ability.charAt(0) }}</span
            >
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
      <!-- TODO (v1.15): This section will render room sprite and dweller sprites in the future -->
      <div class="section room-preview-section">
        <h3 class="section-title">
          <Icon icon="mdi:image-outline" class="h-5 w-5" />
          Room Preview
        </h3>
        <div class="preview-container">
          <!-- Room Image with Dwellers Inside -->
          <div class="room-image-container">
            <img
              v-if="props.room?.image_url"
              :src="roomImageUrl"
              :alt="props.room?.name || 'Room'"
              class="room-image"
            />
            <div class="room-image-placeholder" :class="{ 'has-image': props.room?.image_url }">
              <template v-if="!props.room?.image_url">
                <Icon icon="mdi:home-variant-outline" class="h-16 w-16 opacity-30" />
                <p class="placeholder-text">Room Sprite</p>
                <p class="placeholder-subtext">No Image Available</p>
              </template>

              <!-- Dweller Sprites Container - Positioned Over Room -->
              <div class="dweller-sprites-overlay">
                <div
                  v-for="slot in dwellerCapacity"
                  :key="`slot-${slot}`"
                  class="dweller-sprite-slot"
                  :class="{
                    'slot-filled': assignedDwellers[slot - 1],
                  }"
                >
                  <template v-if="assignedDwellers[slot - 1]">
                    <div class="placeholder-dweller">
                      <span class="dweller-initial">{{
                        assignedDwellers[slot - 1]?.first_name[0]
                      }}</span>
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
            <span class="info-value"
              >{{ Math.ceil((room.size || room.size_min) / 3) }}x merged</span
            >
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
            <div class="stat-value">
              {{ productionInfo.resourceType }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Production Rate</div>
            <div class="stat-value">{{ productionInfo.productionPerMinute }} /min</div>
            <div class="stat-subvalue">{{ productionInfo.productionPerSecond }} /sec</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Efficiency</div>
            <div
              class="stat-value"
              :class="{
                'text-success': productionInfo.isFullyStaffed,
              }"
            >
              {{ productionInfo.efficiency }}%
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Total Stat Points</div>
            <div class="stat-value">
              {{ productionInfo.abilitySum }}
            </div>
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

          <!-- Radio Studio Controls -->
          <div v-if="isRadioRoom" class="radio-controls">
            <div class="radio-header">
              <h4 class="radio-title">Radio Studio</h4>
              <div class="radio-status">
                <span
                  class="status-dot"
                  :class="{
                    active: localRadioMode === 'recruitment',
                  }"
                ></span>
                {{ localRadioMode === 'recruitment' ? 'Recruiting' : 'Broadcasting' }}
              </div>
            </div>

            <!-- Mode Switch -->
            <div class="radio-mode-switch">
              <button
                @click="handleSwitchRadioMode('recruitment')"
                class="mode-btn"
                :class="{
                  active: localRadioMode === 'recruitment',
                }"
              >
                <Icon icon="mdi:radio-tower" class="h-4 w-4" />
                Recruitment
              </button>
              <button
                @click="handleSwitchRadioMode('happiness')"
                class="mode-btn"
                :class="{
                  active: localRadioMode === 'happiness',
                }"
              >
                <Icon icon="mdi:emoticon-happy" class="h-4 w-4" />
                Happiness
              </button>
            </div>

            <!-- Staffing Warning -->
            <UAlert v-if="assignedDwellers.length === 0" variant="warning" class="mb-3">
              <Icon icon="mdi:alert" class="h-4 w-4" />
              Assign at least one dweller to operate the radio room before recruiting.
            </UAlert>

            <!-- Recruit Dweller Button -->
            <UButton
              @click="handleRecruitDweller"
              :disabled="
                isRecruiting || assignedDwellers.length === 0 || localRadioMode !== 'recruitment'
              "
              variant="primary"
              class="recruit-btn"
            >
              <Icon icon="mdi:account-plus" class="h-5 w-5" />
              <span>Recruit Dweller ({{ manualRecruitCost }} caps)</span>
            </UButton>
          </div>

          <!-- Rush Production Button (Placeholder) -->
          <UButton
            v-else-if="productionInfo"
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
          <UTooltip v-if="isVaultDoor" text="The Vault Door is vital and cannot be destroyed.">
            <UButton disabled variant="danger" class="action-btn">
              <Icon icon="mdi:delete" class="h-5 w-5" />
              <span>Destroy Room</span>
            </UButton>
          </UTooltip>
          <UButton
            v-else
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
  border-bottom: 1px solid var(--color-theme-glow);
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
  color: var(--color-theme-primary);
  margin: 0;
}

.room-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-terminal-green);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
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
  color: var(--color-theme-primary);
  cursor: pointer;
  padding: 0.5rem;
  transition: all 0.2s;
}

.close-btn:hover {
  color: var(--color-theme-primary);
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
  color: var(--color-theme-primary);
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
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
}

.info-label {
  color: #aaa;
  font-size: 0.875rem;
  flex-shrink: 0;
}

.info-value {
  color: var(--color-theme-primary);
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
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
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
  color: var(--color-theme-primary);
  margin-top: 0.5rem;
}

.stat-subvalue {
  font-size: 0.75rem;
  color: #888;
  margin-top: 0.25rem;
}

.text-success {
  color: #00ff00 !important;
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.dweller-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--color-theme-glow);
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
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  transition: all 0.2s;
}

.dweller-card.clickable {
  cursor: pointer;
}

.dweller-card.clickable:hover {
  background: rgba(0, 0, 0, 0.5);
  border-color: var(--color-theme-primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--color-theme-glow);
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
  color: var(--color-theme-primary);
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
  color: var(--color-theme-primary);
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
  flex: 1 1 200px;
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
  background: rgba(0, 0, 0, 0.2);
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--color-theme-glow);
}

.preview-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.room-image-container {
  position: relative;
  min-height: 150px;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid var(--color-theme-glow);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.8);
}

.room-image {
  width: 100%;
  height: auto;
  max-height: 300px;
  object-fit: contain;
  background: rgba(0, 0, 0, 0.8);
  display: block;
}

.room-image-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  padding: 1.25rem;
}

.room-image-placeholder.has-image {
  background: transparent;
  pointer-events: none;
}

@keyframes pulse-border {
  0%,
  100% {
    border-color: var(--color-theme-glow);
  }
  50% {
    border-color: var(--color-theme-primary);
  }
}

.placeholder-text {
  margin: 1rem 0 0.25rem;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-theme-primary);
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
  left: 1rem;
  right: 1rem;
  display: flex;
  justify-content: space-evenly;
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
  background: rgba(0, 0, 0, 0.3);
  border: 2px dashed var(--color-theme-glow);
  border-radius: 8px;
  transition: all 0.3s;
}

.placeholder-dweller.empty {
  background: rgba(128, 128, 128, 0.05);
  border-color: rgba(128, 128, 128, 0.2);
}

.slot-filled .placeholder-dweller {
  background: rgba(0, 0, 0, 0.4);
  border: 2px solid var(--color-theme-primary);
  animation: glow-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%,
  100% {
    box-shadow: 0 0 8px var(--color-theme-glow);
  }
  50% {
    box-shadow: 0 0 16px var(--color-theme-primary);
  }
}

.dweller-initial {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.dweller-slot-name {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-theme-primary);
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

/* Room upgrade animation */
.tier-upgraded {
  animation: tier-upgrade-pulse 1s ease-out;
  color: var(--color-terminal-green) !important;
  font-weight: bold;
}

@keyframes tier-upgrade-pulse {
  0% {
    transform: scale(1);
    filter: drop-shadow(0 0 0px var(--color-theme-glow));
  }
  25% {
    transform: scale(1.2);
    filter: drop-shadow(0 0 8px var(--color-theme-glow));
  }
  50% {
    transform: scale(1.1);
    filter: drop-shadow(0 0 12px var(--color-theme-glow));
  }
  75% {
    transform: scale(1.15);
    filter: drop-shadow(0 0 8px var(--color-theme-glow));
  }
  100% {
    transform: scale(1);
    filter: drop-shadow(0 0 4px var(--color-theme-glow));
  }
}

/* Radio Studio Controls */
.radio-controls {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  margin-top: 0.5rem;
  width: 100%;
}

.radio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.radio-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.radio-status {
  font-size: 0.75rem;
  color: #888;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  text-transform: uppercase;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #555;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.5);
}

.status-dot.active {
  background-color: var(--color-terminal-green);
  box-shadow: 0 0 8px var(--color-terminal-green);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.5;
  }
}

.radio-mode-switch {
  display: flex;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 6px;
  padding: 4px;
  gap: 4px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border: none;
  background: transparent;
  color: #888;
  cursor: pointer;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s;
}

.mode-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #aaa;
}

.mode-btn.active {
  background: var(--color-theme-primary);
  color: #000;
  font-weight: bold;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.recruit-btn {
  width: 100%;
  margin-top: 0.5rem;
}
</style>
