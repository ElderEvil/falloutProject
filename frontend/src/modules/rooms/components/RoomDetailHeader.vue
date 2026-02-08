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
      <h2 class="room-title">
        <Icon :icon="resourceIcon" class="room-icon" />
        {{ roomName }}
      </h2>
      <div class="header-metadata">
        <span class="metadata-item">{{ category }} Room</span>
        <span class="metadata-divider">&middot;</span>
        <span class="metadata-item" :class="{ 'tier-upgraded': justUpgraded }"
          >Tier {{ tier }}</span
        >
        <span v-if="ability" class="metadata-divider">&middot;</span>
        <span v-if="ability" class="metadata-item"
          >Requires: {{ ability.charAt(0) }}</span
        >
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-header {
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--color-theme-glow);
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.room-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.25rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  margin: 0;
}

.room-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-terminal-green);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.header-metadata {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metadata-item {
  color: #888;
}

.metadata-divider {
  color: #555;
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
