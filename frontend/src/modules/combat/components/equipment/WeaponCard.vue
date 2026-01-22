<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Weapon } from '../../models/equipment'
import { getRarityColor, getDamageRange } from '../../models/equipment'

interface Props {
  weapon: Weapon
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

const rarityColor = computed(() => getRarityColor(props.weapon.rarity))
const damageRange = computed(() => getDamageRange(props.weapon))

const weaponIcon = computed(() => {
  switch (props.weapon.weapon_subtype) {
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
})
</script>

<template>
  <div class="weapon-card" :class="{ equipped }">
    <div class="weapon-header">
      <Icon :icon="weaponIcon" class="weapon-icon" />
      <div class="weapon-info">
        <h4 class="weapon-name" :style="{ color: rarityColor }">{{ weapon.name }}</h4>
        <p class="weapon-type">{{ weapon.weapon_subtype }} • {{ weapon.rarity }}</p>
      </div>
    </div>

    <p class="weapon-description">{{ weapon.description }}</p>

    <div class="weapon-stats">
      <div class="stat-item">
        <Icon icon="mdi:sword-cross" class="stat-icon" />
        <span class="stat-label">Damage:</span>
        <span class="stat-value">{{ damageRange }}</span>
      </div>
      <div class="stat-item">
        <Icon icon="mdi:alphabet-latin" class="stat-icon" />
        <span class="stat-label">Uses:</span>
        <span class="stat-value">{{ weapon.stat }}</span>
      </div>
      <div v-if="weapon.accuracy" class="stat-item">
        <Icon icon="mdi:target" class="stat-icon" />
        <span class="stat-label">Accuracy:</span>
        <span class="stat-value">{{ weapon.accuracy }}%</span>
      </div>
    </div>

    <div v-if="showActions" class="weapon-actions">
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
.weapon-card {
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  padding: 1rem;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.weapon-card:hover {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--color-theme-glow);
}

.weapon-card.equipped {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 12px var(--color-theme-glow);
}

.weapon-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.weapon-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.weapon-info {
  flex: 1;
}

.weapon-name {
  font-size: 1.125rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
  text-shadow: 0 0 4px currentColor;
}

.weapon-type {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-transform: capitalize;
}

.weapon-description {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
  line-height: 1.4;
}

.weapon-stats {
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

.weapon-actions {
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
