<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { RewardsSummary } from '@/stores/exploration'

interface Props {
  rewards: RewardsSummary | null
  dwellerName: string
  show: boolean
}

const props = defineProps<Props>()

// Guard against null rewards
const safeRewards = computed(() => props.rewards || {
  caps: 0,
  items: [],
  experience: 0,
  distance: 0,
  enemies_defeated: 0,
  events_encountered: 0
})
const emit = defineEmits<{
  close: []
}>()

const getRarityColor = (rarity: string): string => {
  const colors: Record<string, string> = {
    Common: '#808080',
    Rare: '#4169E1',
    Legendary: '#FFD700'
  }
  return colors[rarity] || colors.Common
}
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click="emit('close')">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <div class="header-title">
            <Icon icon="mdi:treasure-chest" class="header-icon" />
            <h2 class="title">Exploration Complete!</h2>
          </div>
          <button @click="emit('close')" class="close-btn">
            <Icon icon="mdi:close" />
          </button>
        </div>

        <div class="modal-body">
          <!-- Dweller Name -->
          <div class="dweller-name">
            <Icon icon="mdi:account-check" class="mr-2" />
            {{ dwellerName }} has returned from the wasteland!
          </div>

          <!-- Recalled Early Banner -->
          <div v-if="safeRewards.recalled_early" class="recalled-banner">
            <Icon icon="mdi:information" class="mr-2" />
            Recalled early ({{ Math.round(safeRewards.progress_percentage || 0) }}% complete) - Reduced rewards
          </div>

          <!-- Rewards Grid -->
          <div class="rewards-grid">
            <!-- Experience -->
            <div class="reward-card experience-card">
              <div class="reward-icon-container experience">
                <Icon icon="mdi:star" class="reward-icon" />
              </div>
              <div class="reward-details">
                <div class="reward-label">Experience Gained</div>
                <div class="reward-value experience-value">+{{ safeRewards.experience }} XP</div>
              </div>
            </div>

            <!-- Caps -->
            <div class="reward-card caps-card">
              <div class="reward-icon-container caps">
                <Icon icon="mdi:currency-usd" class="reward-icon" />
              </div>
              <div class="reward-details">
                <div class="reward-label">Bottle Caps</div>
                <div class="reward-value caps-value">{{ safeRewards.caps }}</div>
              </div>
            </div>

            <!-- Distance -->
            <div class="reward-card">
              <div class="reward-icon-container distance">
                <Icon icon="mdi:map-marker-distance" class="reward-icon" />
              </div>
              <div class="reward-details">
                <div class="reward-label">Distance Traveled</div>
                <div class="reward-value">{{ safeRewards.distance }} miles</div>
              </div>
            </div>

            <!-- Enemies -->
            <div class="reward-card">
              <div class="reward-icon-container enemies">
                <Icon icon="mdi:skull" class="reward-icon" />
              </div>
              <div class="reward-details">
                <div class="reward-label">Enemies Defeated</div>
                <div class="reward-value">{{ safeRewards.enemies_defeated }}</div>
              </div>
            </div>

            <!-- Events -->
            <div class="reward-card">
              <div class="reward-icon-container events">
                <Icon icon="mdi:map-marker-alert" class="reward-icon" />
              </div>
              <div class="reward-details">
                <div class="reward-label">Events Encountered</div>
                <div class="reward-value">{{ safeRewards.events_encountered }}</div>
              </div>
            </div>
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
        </div>

        <div class="modal-footer">
          <button @click="emit('close')" class="collect-btn">
            <Icon icon="mdi:check-bold" class="mr-2" />
            Collect Rewards
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  backdrop-filter: blur(4px);
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-content {
  background: #0a0a0a;
  border: 2px solid #00ff00;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 40px rgba(0, 255, 0, 0.4);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 2px solid rgba(0, 255, 0, 0.3);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  width: 2rem;
  height: 2rem;
  color: #FFD700;
  filter: drop-shadow(0 0 8px rgba(255, 215, 0, 0.6));
}

.title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 10px rgba(0, 255, 0, 0.6);
}

.close-btn {
  background: transparent;
  border: 2px solid rgba(0, 255, 0, 0.5);
  color: #00ff00;
  padding: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
}

.close-btn:hover {
  background: rgba(0, 128, 0, 0.3);
  border-color: #00ff00;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.dweller-name {
  display: flex;
  align-items: center;
  font-size: 1.125rem;
  font-weight: 600;
  color: #00ff00;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.5);
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: rgba(0, 255, 0, 0.05);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 4px;
}

.recalled-banner {
  display: flex;
  align-items: center;
  font-size: 0.875rem;
  color: #ffa500;
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

.reward-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: rgba(0, 255, 0, 0.03);
  border: 2px solid rgba(0, 255, 0, 0.2);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.reward-card:hover {
  background: rgba(0, 255, 0, 0.08);
  border-color: rgba(0, 255, 0, 0.4);
  transform: translateY(-2px);
}

.experience-card {
  grid-column: 1 / -1;
}

.caps-card {
  grid-column: 1 / -1;
}

.reward-icon-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.reward-icon-container.experience {
  background: rgba(255, 215, 0, 0.2);
  border: 2px solid #FFD700;
}

.reward-icon-container.caps {
  background: rgba(0, 255, 0, 0.2);
  border: 2px solid #00ff00;
}

.reward-icon-container.distance {
  background: rgba(65, 105, 225, 0.2);
  border: 2px solid #4169E1;
}

.reward-icon-container.enemies {
  background: rgba(255, 0, 0, 0.2);
  border: 2px solid #ff0000;
}

.reward-icon-container.events {
  background: rgba(255, 165, 0, 0.2);
  border: 2px solid #ffa500;
}

.reward-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: inherit;
}

.reward-icon-container.experience .reward-icon {
  color: #FFD700;
}

.reward-icon-container.caps .reward-icon {
  color: #00ff00;
}

.reward-icon-container.distance .reward-icon {
  color: #4169E1;
}

.reward-icon-container.enemies .reward-icon {
  color: #ff0000;
}

.reward-icon-container.events .reward-icon {
  color: #ffa500;
}

.reward-details {
  flex: 1;
}

.reward-label {
  font-size: 0.75rem;
  color: rgba(0, 255, 0, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.reward-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
}

.experience-value {
  color: #FFD700;
  text-shadow: 0 0 8px rgba(255, 215, 0, 0.6);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

.caps-value {
  color: #00ff00;
}

.items-section {
  margin-top: 1.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  font-size: 1.125rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.5);
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid rgba(0, 255, 0, 0.3);
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
  color: rgba(0, 255, 0, 0.7);
}

.item-check {
  width: 1.5rem;
  height: 1.5rem;
  color: #00ff00;
  flex-shrink: 0;
}

.no-items {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 3rem 2rem;
  color: rgba(0, 255, 0, 0.5);
}

.no-items-icon {
  width: 4rem;
  height: 4rem;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 2px solid rgba(0, 255, 0, 0.3);
}

.collect-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 1rem;
  background: rgba(0, 128, 0, 0.3);
  border: 2px solid #00ff00;
  border-radius: 6px;
  color: #00ff00;
  font-size: 1.125rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.5);
}

.collect-btn:hover {
  background: rgba(0, 180, 0, 0.4);
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
  transform: translateY(-2px);
}

/* Scrollbar */
.modal-body::-webkit-scrollbar {
  width: 8px;
}

.modal-body::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb {
  background: #00ff00;
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: #00cc00;
}
</style>
