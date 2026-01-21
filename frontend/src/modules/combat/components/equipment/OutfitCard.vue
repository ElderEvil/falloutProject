<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Outfit } from '@/models/equipment'
import { getRarityColor, getOutfitBonuses } from '@/models/equipment'

interface Props {
  outfit: Outfit
  showActions?: boolean
  equipped?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showActions: false,
  equipped: false
})

const emit = defineEmits<{
  (e: 'equip'): void
  (e: 'unequip'): void
}>()

const rarityColor = computed(() => getRarityColor(props.outfit.rarity))
const bonuses = computed(() => getOutfitBonuses(props.outfit))

const outfitIcon = computed(() => {
  switch (props.outfit.outfit_type) {
    case 'common_outfit':
      return 'mdi:tshirt-crew'
    case 'rare_outfit':
      return 'mdi:hard-hat'
    case 'legendary_outfit':
      return 'mdi:shield'
    case 'power_armor':
      return 'mdi:robot'
    case 'tiered_outfit':
      return 'mdi:star'
    default:
      return 'mdi:tshirt-crew'
  }
})
</script>

<template>
  <div class="outfit-card" :class="{ equipped }">
    <div class="outfit-header">
      <Icon :icon="outfitIcon" class="outfit-icon" />
      <div class="outfit-info">
        <h4 class="outfit-name" :style="{ color: rarityColor }">{{ outfit.name }}</h4>
        <p class="outfit-type">{{ outfit.outfit_type }} • {{ outfit.rarity }}</p>
      </div>
    </div>

    <p class="outfit-description">{{ outfit.description }}</p>

    <div v-if="bonuses.length > 0" class="outfit-bonuses">
      <div class="bonuses-header">
        <Icon icon="mdi:chevron-up" class="bonus-icon" />
        <span class="bonuses-label">SPECIAL Bonuses:</span>
      </div>
      <div class="bonuses-grid">
        <div v-for="bonus in bonuses" :key="bonus.stat" class="bonus-item">
          <span class="bonus-stat">{{ bonus.stat }}</span>
          <span class="bonus-value">+{{ bonus.bonus }}</span>
        </div>
      </div>
    </div>

    <div v-if="showActions" class="outfit-actions">
      <button v-if="!equipped" @click="emit('equip')" class="action-btn equip-btn">
        <Icon icon="mdi:check" />
        Equip
      </button>
      <button v-else @click="emit('unequip')" class="action-btn unequip-btn">
        <Icon icon="mdi:close" />
        Unequip
      </button>
    </div>
  </div>
</template>

<style scoped>
.outfit-card {
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  padding: 1rem;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.outfit-card:hover {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--color-theme-glow);
}

.outfit-card.equipped {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 12px var(--color-theme-glow);
}

.outfit-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.outfit-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.outfit-info {
  flex: 1;
}

.outfit-name {
  font-size: 1.125rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
  text-shadow: 0 0 4px currentColor;
}

.outfit-type {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-transform: capitalize;
}

.outfit-description {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
  line-height: 1.4;
}

.outfit-bonuses {
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.bonuses-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.bonus-icon {
  width: 1rem;
  height: 1rem;
  color: var(--color-theme-primary);
}

.bonuses-label {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  font-weight: 600;
}

.bonuses-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.bonus-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  font-size: 0.875rem;
}

.bonus-stat {
  color: var(--color-theme-primary);
  opacity: 0.7;
  font-weight: 600;
}

.bonus-value {
  color: var(--color-theme-primary);
  font-weight: 700;
}

.outfit-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  font-weight: 600;
  font-size: 0.875rem;
  transition: all 0.2s ease;
  cursor: pointer;
}

.equip-btn {
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.equip-btn:hover {
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 12px var(--color-theme-glow);
}

.unequip-btn {
  background: rgba(128, 0, 0, 0.3);
  border: 2px solid #ff0000;
  color: #ff0000;
}

.unequip-btn:hover {
  background: rgba(128, 0, 0, 0.5);
  box-shadow: 0 0 12px rgba(255, 0, 0, 0.4);
}
</style>
