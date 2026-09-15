<script setup lang="ts">
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
  <div class="room-command-bar">
    <p v-if="upgradeInfo && !upgradeInfo.canUpgrade && upgradeInfo.maxTier > 1" class="command-status">
      Max tier reached ({{ room.tier }}/{{ upgradeInfo.maxTier }})
    </p>

    <UButton
      v-if="upgradeInfo?.canUpgrade"
      @click="emit('upgrade')"
      :disabled="isUpgrading"
      variant="primary"
      size="sm"
    >
      <Icon icon="mdi:arrow-up-circle" class="h-4 w-4" />
      Upgrade to Tier {{ upgradeInfo.nextTier }}
      <span class="cost-readout">{{ upgradeInfo.upgradeCost }} caps</span>
    </UButton>

    <UButton
      @click="emit('unassignAll')"
      :disabled="assignedDwellerCount === 0"
      variant="secondary"
      size="sm"
    >
      <Icon icon="mdi:account-remove" class="h-4 w-4" />
      Unassign All Dwellers
    </UButton>

    <UTooltip v-if="isVaultDoor" text="The Vault Door is vital and cannot be destroyed.">
      <UButton disabled variant="danger" size="sm">
        <Icon icon="mdi:delete" class="h-4 w-4" />
        Destroy Room
      </UButton>
    </UTooltip>
    <UButton v-else @click="emit('destroy')" :disabled="isDestroying" variant="danger" size="sm">
      <Icon icon="mdi:delete" class="h-4 w-4" />
      Destroy Room
    </UButton>
  </div>
</template>

<style scoped>
.room-command-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.5rem;
  border-top: 1px solid color-mix(in srgb, var(--color-theme-primary) 25%, transparent);
  padding-top: 0.75rem;
}

.cost-readout {
  margin-left: auto;
  padding-left: 0.5rem;
  background: var(--color-surface-sunken);
  color: var(--color-warning);
  font-size: 0.6875rem;
  font-weight: bold;
}

.command-status {
  margin: 0 auto 0 0;
  color: color-mix(in srgb, var(--color-theme-primary) 58%, transparent);
  font-size: 0.6875rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

@media (max-width: 480px) {
  .room-command-bar {
    justify-content: space-between;
  }
}
</style>
