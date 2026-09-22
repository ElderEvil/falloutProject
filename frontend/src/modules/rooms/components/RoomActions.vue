<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'
import { Button } from '@/core/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'

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
  isVaultDoor: boolean
  assignedDwellerCount: number
}

defineProps<Props>()

const emit = defineEmits<{
  upgrade: []
  destroy: []
  unassignAll: []
}>()
</script>

<template>
  <div class="section room-management">
    <h3 class="section-title">
      <Icon icon="mdi:cog" class="h-5 w-5" />
      Management
    </h3>
    <div class="actions-grid">
      <Button
        v-if="upgradeInfo?.canUpgrade"
        @click="emit('upgrade')"
        :disabled="isUpgrading"
        variant="secondary"
        size="sm"
        class="action-btn action-btn--upgrade justify-start"
      >
        <Icon icon="mdi:arrow-up-circle" class="h-4 w-4" />
        <span>Upgrade to Tier {{ upgradeInfo.nextTier }}</span>
        <span class="cost-badge">{{ upgradeInfo.upgradeCost }} caps</span>
      </Button>
      <Button
        v-else-if="upgradeInfo && upgradeInfo.maxTier > 1"
        disabled
        variant="secondary"
        size="sm"
        class="action-btn action-btn--upgrade justify-start"
      >
        <Icon icon="mdi:arrow-up-circle" class="h-4 w-4" />
        <span>Max tier reached ({{ room.tier }}/{{ upgradeInfo.maxTier }})</span>
      </Button>

      <Button
        @click="emit('unassignAll')"
        :disabled="assignedDwellerCount === 0"
        variant="secondary"
        size="sm"
        class="action-btn action-btn--half justify-start"
      >
        <Icon icon="mdi:account-remove" class="h-4 w-4" />
        Unassign All Dwellers
      </Button>

      <TooltipProvider v-if="isVaultDoor" :delay-duration="200">
        <Tooltip>
          <TooltipTrigger as-child>
            <Button disabled variant="secondary" size="sm" class="action-btn action-btn--half destroy-btn justify-start">
              <Icon icon="mdi:delete" class="h-4 w-4" />
              Destroy Room
            </Button>
          </TooltipTrigger>
          <TooltipContent>The Vault Door is vital and cannot be destroyed.</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <Button
        v-else
        @click="emit('destroy')"
        :disabled="isDestroying"
        variant="secondary"
        size="sm"
        class="action-btn action-btn--half destroy-btn justify-start"
      >
        <Icon icon="mdi:delete" class="h-4 w-4" />
        Destroy Room
      </Button>
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
  gap: 0.75rem;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
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
  color: var(--color-warning);
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
}
</style>
