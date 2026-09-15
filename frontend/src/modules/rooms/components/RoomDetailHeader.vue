<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  roomName: string
  category: string
  tier: number
  ability: string | null
  resourceIcon: string
  justUpgraded: boolean
}

defineProps<Props>()
</script>

<template>
  <div class="modal-header">
    <div class="header-content">
      <div class="title-row">
        <h2 class="room-title">
          <Icon :icon="resourceIcon" class="room-icon" />
          {{ roomName }}
        </h2>
        <span class="tier-readout" :class="{ 'tier-upgraded': justUpgraded }">Tier {{ tier }}</span>
      </div>
      <div class="header-metadata">
        <span class="metadata-item">{{ category }} system</span>
        <span v-if="ability" class="metadata-divider">&middot;</span>
        <span v-if="ability" class="metadata-item">{{ ability.charAt(0) }}-linked</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-header {
  padding-bottom: 0.1rem;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.room-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  font-size: 1rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  margin: 0;
}

.room-icon {
  width: 1.1rem;
  height: 1.1rem;
  color: var(--color-terminal-green);
}

.tier-readout {
  margin-left: auto;
  padding: 0.15rem 0.35rem;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 45%, transparent);
  color: var(--color-warning);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.header-metadata {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.6rem;
  color: color-mix(in srgb, var(--color-theme-primary) 58%, transparent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metadata-item {
  color: inherit;
}

.metadata-divider {
  color: color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.tier-upgraded {
  animation: tier-upgrade-pulse 1s ease-out;
  color: var(--color-terminal-green) !important;
  font-weight: bold;
}

@keyframes tier-upgrade-pulse {
  0% {
    transform: scale(1);
    filter: drop-shadow(0 0 0px var(--color-theme-glow));
  }
  25% {
    transform: scale(1.2);
    filter: drop-shadow(0 0 8px var(--color-theme-glow));
  }
  50% {
    transform: scale(1.1);
    filter: drop-shadow(0 0 12px var(--color-theme-glow));
  }
  75% {
    transform: scale(1.15);
    filter: drop-shadow(0 0 8px var(--color-theme-glow));
  }
  100% {
    transform: scale(1);
    filter: drop-shadow(0 0 4px var(--color-theme-glow));
  }
}
</style>
