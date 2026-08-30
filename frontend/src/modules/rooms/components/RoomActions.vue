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
  assignedDwellerCount: number
}

const props = defineProps<Props>()

const maxTierText = computed(
  () => `Max tier reached (${props.room.tier}/${props.upgradeInfo?.maxTier ?? 'N/A'})`
)

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
      <!-- Radio controls slot: rendered above the action buttons for radio rooms -->
      <slot name="radio-controls" />

      <!-- Upgrade Button -->
      <UButton
        v-if="upgradeInfo?.canUpgrade"
        @click="emit('upgrade')"
        :disabled="isUpgrading"
        variant="secondary"
        size="sm"
        class="action-btn action-btn--upgrade"
      >
        <Icon icon="mdi:arrow-up-circle" class="h-4 w-4" />
        <span>Upgrade to Tier {{ upgradeInfo.nextTier }}</span>
        <span class="cost-badge">{{ upgradeInfo.upgradeCost }} caps</span>
      </UButton>
      <div v-else class="disabled-action">
        <Icon icon="mdi:arrow-up-circle" class="h-4 w-4 opacity-50" />
        <span> {{ maxTierText }} </span>
      </div>

      <!-- Rush Production Button -->
      <UButton
        v-if="hasProductionInfo"
        @click="emit('rushProduction')"
        :disabled="isRushing || assignedDwellerCount === 0"
        variant="secondary"
        size="sm"
        class="action-btn"
      >
        <Icon icon="mdi:lightning-bolt" class="h-4 w-4" />
        <span>Rush Production</span>
        <span class="feature-badge">Coming Soon</span>
      </UButton>

      <!-- Unassign All Button -->
      <UButton
        @click="emit('unassignAll')"
        :disabled="assignedDwellerCount === 0"
        variant="secondary"
        size="sm"
        class="action-btn action-btn--half"
      >
        <Icon icon="mdi:account-remove" class="h-4 w-4" />
        <span>Unassign All Dwellers</span>
      </UButton>

      <!-- Destroy Button -->
      <UTooltip v-if="isVaultDoor" text="The Vault Door is vital and cannot be destroyed.">
        <UButton disabled variant="secondary" size="sm" class="action-btn action-btn--half destroy-btn">
          <Icon icon="mdi:delete" class="h-4 w-4" />
          <span>Destroy Room</span>
        </UButton>
      </UTooltip>
      <UButton
        v-else
        @click="emit('destroy')"
        :disabled="isDestroying"
        variant="secondary"
        size="sm"
        class="action-btn action-btn--half destroy-btn"
      >
        <Icon icon="mdi:delete" class="h-4 w-4" />
        <span>Destroy Room</span>
      </UButton>
    </div>
  </div>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  margin: 0;
}

.section-title :deep(svg) {
  width: 0.875rem;
  height: 0.875rem;
}

.actions-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.25rem 0 0;
}

.action-btn {
  flex: 1 1 200px;
  min-width: 200px;
}

.action-btn :deep(button) {
  justify-content: flex-start;
}

.action-btn.destroy-btn {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.action-btn.destroy-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--color-danger) 12%, transparent);
  box-shadow: none;
}

.cost-badge {
  margin-left: auto;
  padding: 0.125rem 0.5rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-warning);
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--color-warning);
}

.feature-badge {
  margin-left: auto;
  padding: 0.125rem 0.5rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-info);
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: bold;
  color: var(--color-info);
  font-style: italic;
}

.disabled-action {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  color: var(--color-gray-500);
  font-size: 0.875rem;
}
</style>
