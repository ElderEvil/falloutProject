<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton, UModal } from '@/core/components/ui'
import RewardCard from '@/core/components/common/RewardCard.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { useExplorationStore, type RewardsSummary } from '@/modules/exploration/stores/exploration'
import { getRarityColor } from '@/modules/exploration/models/exploration'

interface Props {
  rewards: RewardsSummary | null
  dwellerName: string
  show: boolean
  explorationId?: string
}

const props = withDefaults(defineProps<Props>(), { explorationId: '' })
const toast = useToast()
const authStore = useAuthStore()
const explorationStore = useExplorationStore()

// Guard against null rewards
const safeRewards = computed(
  () =>
    props.rewards || {
      caps: 0,
      items: [],
      overflow_items: [],
      experience: 0,
      distance: 0,
      enemies_defeated: 0,
      events_encountered: 0,
    }
)
const emit = defineEmits<{
  close: []
  resolved: []
}>()

// Overflow items live here until each is Taken or Sold; the backend holds the
// source of truth and every action replaces this list from its response.
const unclaimed = ref([...(props.rewards?.overflow_items ?? [])])
watch(
  () => props.rewards,
  (rewards) => {
    unclaimed.value = [...(rewards?.overflow_items ?? [])]
  }
)

const hasOverflow = computed(() => unclaimed.value.length > 0)
const resolvedExplorationId = computed(() => safeRewards.value.exploration_id || props.explorationId)
const busyIndex = ref<number | null>(null)
const legacyOverflow = ref(false)
const requiresResolution = computed(() => hasOverflow.value && !legacyOverflow.value)

const resolveOverflow = async (action: 'take' | 'sell', index: number) => {
  if (!resolvedExplorationId.value || !authStore.token || busyIndex.value !== null) return undefined
  const name = unclaimed.value[index]?.item_name ?? 'Item'
  busyIndex.value = index
  try {
    const result = await explorationStore.resolveOverflowItem(
      resolvedExplorationId.value,
      action,
      index,
      authStore.token
    )
    unclaimed.value = result.unclaimed_loot
    emit('resolved')
    toast.success(action === 'take' ? `Stored ${name}` : `Sold ${name} for +${result.caps_granted} caps`)
    return result
  } catch (error) {
    if ((error as { response?: { status?: number } }).response?.status === 404) {
      legacyOverflow.value = true
      toast.info('These items were left behind before overflow resolution was available')
      return undefined
    }
    throw error
  } finally {
    busyIndex.value = null
  }
}

const sellAll = async () => {
  while (unclaimed.value.length > 0) {
    if (!(await resolveOverflow('sell', 0))) return
  }
}

const tryClose = () => {
  if (requiresResolution.value) {
    toast.info('Storage is full — Take or Sell each item above first')
    return
  }
  emit('close')
}
</script>

<template>
  <UModal
    :model-value="show"
    title="Exploration Complete!"
    size="wide"
    @close="tryClose"
  >
    <template #header="{ titleId }">
      <div class="flex items-center gap-3">
        <Icon icon="mdi:treasure-chest" class="h-8 w-8 text-theme-primary terminal-glow" />
        <h2 :id="titleId" class="text-2xl font-bold text-theme-primary terminal-glow">Exploration Complete!</h2>
      </div>
    </template>
    <template #default>
      <!-- Dweller Name -->
      <div class="dweller-name">
        <Icon icon="mdi:account-check" class="mr-2 h-6 w-6 shrink-0" />
        {{ dwellerName }} has returned from the wasteland!
      </div>

      <!-- Recalled Early Banner -->
      <div v-if="safeRewards.recalled_early" class="recalled-banner">
        <Icon icon="mdi:information" class="mr-2 h-6 w-6 shrink-0" />
        Recalled early ({{ Math.round(safeRewards.progress_percentage || 0) }}% complete) -
        Reduced rewards
      </div>

      <!-- Rewards Grid -->
      <div class="rewards-grid">
        <RewardCard
          icon="mdi:star"
          label="Experience Gained"
          :value="`+${safeRewards.experience} XP`"
          variant="experience"
          span
        />
        <RewardCard
          icon="mdi:currency-usd"
          label="Bottle Caps"
          :value="String(safeRewards.caps)"
          variant="caps"
          span
        />
        <RewardCard
          icon="mdi:map-marker-distance"
          label="Distance Traveled"
          :value="`${safeRewards.distance} miles`"
          variant="distance"
        />
        <RewardCard
          icon="mdi:skull"
          label="Enemies Defeated"
          :value="String(safeRewards.enemies_defeated)"
          variant="enemies"
        />
        <RewardCard
          icon="mdi:map-marker-alert"
          label="Events Encountered"
          :value="String(safeRewards.events_encountered)"
          variant="events"
        />
      </div>

      <!-- Items Found -->
      <div v-if="safeRewards.items && safeRewards.items.length > 0" class="items-section">
        <h3 class="section-title">
          <Icon icon="mdi:package-variant" class="mr-2" />
          {{ requiresResolution ? 'Stored in Vault' : 'Items Found' }}
        </h3>
        <div class="items-list">
          <div
            v-for="(item, index) in safeRewards.items"
            :key="index"
            class="item-entry"
            :style="{ borderColor: getRarityColor(item.rarity) }"
          >
            <div class="item-info">
              <div class="item-name" :style="{ color: getRarityColor(item.rarity) }">
                {{ item.item_name }}
              </div>
              <div class="item-meta">
                <span class="item-rarity" :style="{ color: getRarityColor(item.rarity) }">
                  {{ item.rarity }}
                </span>
                <span class="item-quantity">x{{ item.quantity }}</span>
              </div>
            </div>
            <Icon icon="mdi:check-circle" class="item-check" />
          </div>
        </div>
      </div>

      <div v-else-if="!hasOverflow" class="no-items">
        <Icon icon="mdi:package-variant-closed" class="no-items-icon" />
        <p>No items found during this exploration</p>
      </div>

      <!-- Overflow Items (Storage Full) -->
      <div
        v-if="hasOverflow"
        class="items-section overflow-section"
      >
        <h3 class="section-title overflow-title">
          <Icon icon="mdi:package-variant-closed-remove" class="mr-2" />
          {{ legacyOverflow ? 'Storage Full — Items Left Behind' : 'Storage Full — Needs Decision' }}
        </h3>
        <p v-if="legacyOverflow" class="text-sm text-theme-primary/70">
          This report predates overflow resolution. These items were left behind.
        </p>
        <div v-else class="items-list">
          <div
            v-for="(item, index) in unclaimed"
            :key="`${item.item_name}-${index}`"
            class="item-entry overflow-item"
            :style="{ borderColor: getRarityColor(item.rarity) }"
          >
            <div class="item-info">
              <div class="item-name" :style="{ color: getRarityColor(item.rarity) }">{{ item.item_name }}</div>
              <div class="item-meta">
                <span class="item-rarity" :style="{ color: getRarityColor(item.rarity) }">{{ item.rarity }}</span>
                <span class="item-quantity">x{{ item.quantity }}</span>
              </div>
            </div>
            <div class="overflow-actions">
              <UButton size="sm" :disabled="busyIndex !== null" :loading="busyIndex === index" @click="resolveOverflow('take', index)">
                Take
              </UButton>
              <UButton size="sm" variant="secondary" :disabled="busyIndex !== null" @click="resolveOverflow('sell', index)">
                Sell
              </UButton>
            </div>
          </div>
          <UButton v-if="unclaimed.length > 1" size="sm" variant="secondary" class="sell-all-btn self-end" :disabled="busyIndex !== null" @click="sellAll">
            Sell all remaining
          </UButton>
        </div>
      </div>
    </template>

    <template #footer>
      <button
        @click="tryClose"
        class="collect-btn"
        :disabled="requiresResolution"
        :title="requiresResolution ? 'Take or Sell each item above first' : undefined"
      >
        <Icon icon="mdi:check-bold" class="mr-2" />
        Collect Rewards
      </button>
    </template>
  </UModal>
</template>

<style scoped>
.dweller-name {
  display: flex;
  align-items: center;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: color-mix(in srgb, var(--color-theme-primary) 5%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  border-radius: 4px;
}

.recalled-banner {
  display: flex;
  align-items: center;
  font-size: 0.875rem;
  color: var(--color-warning);
  text-shadow: 0 0 4px rgba(255, 165, 0, 0.5);
  margin-bottom: 1.5rem;
  padding: 0.75rem;
  background: rgba(255, 165, 0, 0.1);
  border: 1px solid rgba(255, 165, 0, 0.3);
  border-radius: 4px;
}

.rewards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.items-section {
  margin-top: 1.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.item-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.overflow-actions {
  display: flex;
  flex-shrink: 0;
  gap: 0.5rem;
}

.item-entry:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 8%, transparent);
  transform: translateX(4px);
}

.item-info {
  flex: 1;
}

.item-name {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.item-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
}

.item-rarity {
  font-weight: 600;
}

.item-quantity {
  color: color-mix(in srgb, var(--color-theme-primary) 70%, transparent);
}

.item-check {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-theme-primary);
  flex-shrink: 0;
}

.no-items {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 3rem 2rem;
  color: color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
}

.no-items-icon {
  width: 4rem;
  height: 4rem;
}

.collect-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 1rem;
  background: color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  border: 2px solid var(--color-theme-primary);
  border-radius: 6px;
  color: var(--color-theme-primary);
  font-size: 1.125rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.collect-btn:hover:not(:disabled) {
  background: var(--color-theme-primary);
  color: var(--color-terminal-background);
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.collect-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
