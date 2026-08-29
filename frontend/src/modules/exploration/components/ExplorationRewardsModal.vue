<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import RewardsModalShell from '@/core/components/common/RewardsModalShell.vue'
import RewardCard from '@/core/components/common/RewardCard.vue'
import type { RewardsSummary } from '@/modules/exploration/stores/exploration'
import { getRarityColor } from '@/modules/exploration/models/exploration'

interface Props {
  rewards: RewardsSummary | null
  dwellerName: string
  show: boolean
}

const props = defineProps<Props>()

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
}>()
</script>

<template>
  <RewardsModalShell
    :show="show"
    title="Exploration Complete!"
    header-icon="mdi:treasure-chest"
    max-width="800px"
    @close="emit('close')"
  >
    <template #default>
      <!-- Dweller Name -->
      <div class="dweller-name">
        <Icon icon="mdi:account-check" class="mr-2" />
        {{ dwellerName }} has returned from the wasteland!
      </div>

      <!-- Recalled Early Banner -->
      <div v-if="safeRewards.recalled_early" class="recalled-banner">
        <Icon icon="mdi:information" class="mr-2" />
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
          Items Found
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

      <div v-else class="no-items">
        <Icon icon="mdi:package-variant-closed" class="no-items-icon" />
        <p>No items found during this exploration</p>
      </div>

      <!-- Overflow Items (Storage Full) -->
      <div
        v-if="safeRewards.overflow_items && safeRewards.overflow_items.length > 0"
        class="items-section overflow-section"
      >
        <h3 class="section-title overflow-title">
          <Icon icon="mdi:package-variant-closed-remove" class="mr-2" />
          Storage Full - Items Left Behind
        </h3>
        <div class="items-list">
          <div
            v-for="(item, index) in safeRewards.overflow_items"
            :key="index"
            class="item-entry overflow-item"
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
            <Icon icon="mdi:close-circle" class="item-check overflow-icon" />
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <button @click="emit('close')" class="collect-btn">
        <Icon icon="mdi:check-bold" class="mr-2" />
        Collect Rewards
      </button>
    </template>
  </RewardsModalShell>
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

.item-entry:hover {
  background: rgba(0, 50, 0, 0.3);
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

.collect-btn:hover {
  background: var(--color-theme-primary);
  color: var(--color-terminal-background);
  box-shadow: 0 0 20px var(--color-theme-glow);
}
</style>
