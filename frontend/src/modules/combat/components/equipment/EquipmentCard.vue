<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Weapon, Outfit } from '@/modules/combat/models/equipment'
import { getRarityColor, getDamageRange, getOutfitBonuses } from '@/modules/combat/models/equipment'

interface Props {
  item: Weapon | Outfit
  type: 'weapon' | 'outfit'
  showActions?: boolean
  equipped?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showActions: false,
  equipped: false,
})

const emit = defineEmits<{
  (e: 'equip'): void
  (e: 'unequip'): void
}>()

const rarityColor = computed(() => getRarityColor(props.item.rarity))

const itemIcon = computed(() => {
  if (props.type === 'weapon') {
    const w = props.item as Weapon
    switch (w.weapon_subtype) {
      case 'pistol':
        return 'mdi:pistol'
      case 'rifle':
        return 'mdi:rifle'
      case 'shotgun':
        return 'mdi:shotgun'
      case 'automatic':
        return 'mdi:rifle'
      case 'explosive':
        return 'mdi:bomb'
      case 'flamer':
        return 'mdi:fire'
      case 'edged':
        return 'mdi:sword'
      case 'blunt':
        return 'mdi:hammer'
      case 'pointed':
        return 'mdi:spear'
      default:
        return 'mdi:pistol'
    }
  }
  const o = props.item as Outfit
  switch (o.outfit_type) {
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

const damageRange = computed(() =>
  props.type === 'weapon' ? getDamageRange(props.item as Weapon) : ''
)

const bonuses = computed(() =>
  props.type === 'outfit' ? getOutfitBonuses(props.item as Outfit) : []
)

const itemTypeLabel = computed(() =>
  props.type === 'weapon'
    ? (props.item as Weapon).weapon_subtype
    : (props.item as Outfit).outfit_type
)
</script>

<template>
  <div class="equipment-card" :class="{ equipped }">
    <div class="equipment-header">
      <Icon :icon="itemIcon" class="equipment-icon" />
      <div class="equipment-info">
        <h4 class="equipment-name" :style="{ color: rarityColor }">{{ item.name }}</h4>
        <p class="equipment-type">{{ itemTypeLabel }} • {{ item.rarity }}</p>
      </div>
    </div>

    <p class="equipment-description">{{ item.description }}</p>

    <!-- Weapon stats -->
    <div v-if="type === 'weapon'" class="equipment-stats">
      <div class="stat-item">
        <Icon icon="mdi:sword-cross" class="stat-icon" />
        <span class="stat-label">Damage:</span>
        <span class="stat-value">{{ damageRange }}</span>
      </div>
      <div class="stat-item">
        <Icon icon="mdi:alphabet-latin" class="stat-icon" />
        <span class="stat-label">Uses:</span>
        <span class="stat-value">{{ (item as Weapon).stat }}</span>
      </div>
      <div v-if="(item as Weapon).accuracy" class="stat-item">
        <Icon icon="mdi:target" class="stat-icon" />
        <span class="stat-label">Accuracy:</span>
        <span class="stat-value">{{ (item as Weapon).accuracy }}%</span>
      </div>
    </div>

    <!-- Outfit bonuses -->
    <div v-else-if="bonuses.length > 0" class="equipment-bonuses">
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

    <div v-if="showActions" class="equipment-actions">
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
.equipment-card {
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  padding: 1rem;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.equipment-card:hover {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--color-theme-glow);
}

.equipment-card.equipped {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 12px var(--color-theme-glow);
}

.equipment-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.equipment-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.equipment-info {
  flex: 1;
}

.equipment-name {
  font-size: 1.125rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
  text-shadow: 0 0 4px currentColor;
}

.equipment-type {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-transform: capitalize;
}

.equipment-description {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
  line-height: 1.4;
}

.equipment-stats {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.stat-icon {
  width: 1rem;
  height: 1rem;
  color: var(--color-theme-primary);
}

.stat-label {
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.stat-value {
  color: var(--color-theme-primary);
  font-weight: 700;
  margin-left: auto;
}

.equipment-bonuses {
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

.equipment-actions {
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
  border: 2px solid var(--color-danger);
  color: var(--color-danger);
}

.unequip-btn:hover {
  background: rgba(128, 0, 0, 0.5);
  box-shadow: 0 0 12px color-mix(in srgb, var(--color-danger) 40%, transparent);
}
</style>
