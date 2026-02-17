<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'
import UButton from '@/core/components/ui/UButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'

interface UpgradeInfo {
  canUpgrade: boolean
  upgradeCost: number
  nextTier: number
  maxTier: number
}

interface Props {
  room: Room
  upgradeInfo: UpgradeInfo | null
  isUpgrading: boolean
  isDestroying: boolean
  isRushing: boolean
  isVaultDoor: boolean
  hasProductionInfo: boolean
  isRadioRoom: boolean
  assignedDwellerCount: number
}

const props = defineProps<Props>()

const maxTierText = computed(() => `Max tier reached (${props.room.tier}/${props.upgradeInfo?.maxTier ?? 'N/A'})`)

const emit = defineEmits<{
  upgrade: []
  destroy: []
  rushProduction: []
  unassignAll: []
}>()
</script>

<template>
  <div class="section">
    <h3 class="section-title">
      <Icon icon="mdi:cog" class="h-5 w-5" />
      Management
    </h3>
    <div class="actions-grid">
      <!-- Upgrade Button -->
      <UButton
        v-if="upgradeInfo?.canUpgrade"
        @click="emit('upgrade')"
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
        <span> {{ maxTierText }} </span>
      </div>

      <!-- Radio controls slot -->
      <slot name="radio-controls" />

      <!-- Rush Production Button (Placeholder) -->
      <UButton
        v-if="!isRadioRoom && hasProductionInfo"
        @click="emit('rushProduction')"
        :disabled="isRushing || assignedDwellerCount === 0"
        variant="primary"
        class="action-btn rush-btn"
      >
        <Icon icon="mdi:lightning-bolt" class="h-5 w-5" />
        <span>Rush Production</span>
        <span class="feature-badge">Coming Soon</span>
      </UButton>

      <!-- Unassign All Button -->
      <UButton
        @click="emit('unassignAll')"
        :disabled="assignedDwellerCount === 0"
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
        @click="emit('destroy')"
        :disabled="isDestroying"
        variant="danger"
        class="action-btn"
      >
        <Icon icon="mdi:delete" class="h-5 w-5" />
        <span>Destroy Room</span>
      </UButton>
    </div>
  </div>
</template>

<style scoped>
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
</style>
