<script setup lang="ts">
import { computed } from 'vue';
import { Icon } from '@iconify/vue';
import UButton from '@/components/ui/UButton.vue';
import UTooltip from '@/components/ui/UTooltip.vue';
import XPProgressBar from '@/components/dwellers/XPProgressBar.vue';
import type { components } from '@/types/api.generated';

type DwellerDetailRead = components['schemas']['DwellerDetailRead'];

interface Props {
  dweller: DwellerDetailRead;
  imageUrl?: string | null;
  loading?: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: 'chat'): void
  (e: 'assign'): void
  (e: 'recall'): void
  (e: 'generate-ai'): void
  (e: 'train'): void
  (e: 'assign-pet'): void
  (e: 'use-stimpack'): void
  (e: 'use-radaway'): void
}>();

const getImageUrl = (imagePath: string) => {
  return imagePath.startsWith('http') ? imagePath : `http://${imagePath}`;
};

const healthPercentage = computed(() => {
  if (!props.dweller.max_health) return 0;
  return (props.dweller.health / props.dweller.max_health) * 100;
});

const canUseStimpack = computed(() => {
  return (props.dweller.stimpack || 0) > 0 && props.dweller.health < props.dweller.max_health;
});

const canUseRadaway = computed(() => {
  return (props.dweller.radaway || 0) > 0 && (props.dweller.radiation || 0) > 0;
});
</script>

<template>
  <div class="dweller-card">
    <!-- Portrait -->
    <div class="portrait-container">
      <template v-if="imageUrl">
        <img
          :src="getImageUrl(imageUrl)"
          alt="Dweller Portrait"
          class="portrait-image"
        />
      </template>
      <template v-else>
        <div class="portrait-placeholder">
          <Icon icon="mdi:account-circle" class="h-48 w-48 text-gray-400" />
        </div>

        <!-- Generate AI Button -->
        <UTooltip text="Generate AI portrait & biography" position="right">
          <button
            @click="emit('generate-ai')"
            class="ai-generate-button"
            :disabled="loading"
          >
            <Icon
              :icon="loading ? 'mdi:loading' : 'mdi:sparkles'"
              class="h-8 w-8 text-green-600"
              :class="{ 'animate-spin': loading }"
            />
          </button>
        </UTooltip>
      </template>
    </div>

    <!-- Core Stats -->
    <div class="stats-container">
      <div class="stat-row">
        <span class="stat-label">Level</span>
        <span class="stat-value">{{ dweller.level }}</span>
      </div>

      <div class="stat-row">
        <span class="stat-label">Health</span>
        <span class="stat-value">{{ dweller.health }} / {{ dweller.max_health }}</span>
      </div>
      <div class="health-bar">
        <div class="health-fill" :style="{ width: `${healthPercentage}%` }"></div>
      </div>

      <div class="stat-row">
        <span class="stat-label">Happiness</span>
        <span class="stat-value">{{ dweller.happiness }}%</span>
      </div>
      <div class="happiness-bar">
        <div class="happiness-fill" :style="{ width: `${dweller.happiness}%` }"></div>
      </div>

      <!-- XP Progress Bar -->
      <XPProgressBar
        :level="dweller.level"
        :current-x-p="dweller.experience"
      />

      <!-- Inventory Stats -->
      <div class="inventory-stats">
        <div class="inventory-item">
          <Icon icon="mdi:medical-bag" class="h-5 w-5 text-green-500" />
          <span class="inventory-value">{{ dweller.stimpack || 0 }}</span>
          <span class="inventory-label">Stimpack</span>
        </div>
        <div class="inventory-item">
          <Icon icon="mdi:radiation" class="h-5 w-5 text-yellow-500" />
          <span class="inventory-value">{{ dweller.radaway || 0 }}</span>
          <span class="inventory-label">RadAway</span>
        </div>
      </div>

      <!-- Radiation Display (if any) -->
      <div v-if="dweller.radiation && dweller.radiation > 0" class="stat-row">
        <span class="stat-label">Radiation</span>
        <span class="stat-value text-yellow-400">{{ dweller.radiation }}</span>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="actions-container">
      <UButton
        variant="primary"
        size="md"
        block
        @click="emit('chat')"
      >
        <Icon icon="mdi:message-text" class="h-5 w-5 mr-2" />
        Chat
      </UButton>

      <UButton
        variant="secondary"
        size="md"
        block
        @click="emit('assign')"
        disabled
      >
        <Icon icon="mdi:office-building" class="h-5 w-5 mr-2" />
        Assign to Room
      </UButton>

      <UButton
        variant="secondary"
        size="md"
        block
        @click="emit('recall')"
        disabled
      >
        <Icon icon="mdi:arrow-u-left-top" class="h-5 w-5 mr-2" />
        Recall
      </UButton>

      <!-- Item Usage Buttons -->
      <div class="item-actions">
        <UButton
          variant="secondary"
          size="md"
          @click="emit('use-stimpack')"
          :disabled="!canUseStimpack || loading"
          class="item-button"
        >
          <Icon icon="mdi:medical-bag" class="h-5 w-5 mr-2 text-green-500" />
          Use Stimpack
        </UButton>

        <UButton
          variant="secondary"
          size="md"
          @click="emit('use-radaway')"
          :disabled="!canUseRadaway || loading"
          class="item-button"
        >
          <Icon icon="mdi:radiation" class="h-5 w-5 mr-2 text-yellow-500" />
          Use RadAway
        </UButton>
      </div>

      <!-- Coming Soon Actions -->
      <div class="coming-soon-section">
        <UTooltip text="Train SPECIAL stats in dedicated training rooms - Coming in Phase 2 (Feb-Mar 2026)">
          <button class="locked-action-button" disabled>
            <Icon icon="mdi:school" class="h-5 w-5" />
            <span>Train Stats</span>
            <Icon icon="mdi:lock" class="h-4 w-4 lock-icon" />
          </button>
        </UTooltip>

        <UTooltip text="Assign a pet companion - Coming in Phase 3 (Mar-Apr 2026)">
          <button class="locked-action-button" disabled>
            <Icon icon="mdi:paw" class="h-5 w-5" />
            <span>Assign Pet</span>
            <Icon icon="mdi:lock" class="h-4 w-4 lock-icon" />
          </button>
        </UTooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dweller-card {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.portrait-container {
  position: relative;
  width: 100%;
  max-width: 300px;
  margin: 0 auto;
}

.portrait-image {
  width: 100%;
  height: auto;
  border-radius: 8px;
  border: 2px solid var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.portrait-placeholder {
  width: 100%;
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  border: 2px dashed var(--color-theme-glow);
  border-radius: 8px;
}

.ai-generate-button {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(31, 41, 55, 0.9);
  border: none;
  border-radius: 50%;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.3s ease;
  animation: pulse-glow 2s ease-in-out infinite;
}

.ai-generate-button:hover:not(:disabled) {
  animation: none;
  box-shadow: 0 0 30px var(--color-theme-primary);
  background: rgba(31, 41, 55, 1);
}

.ai-generate-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 10px var(--color-theme-glow);
  }
  50% {
    box-shadow: 0 0 25px var(--color-theme-primary);
  }
}

.stats-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-weight: 600;
  color: var(--color-theme-primary);
  text-shadow: 0 0 3px var(--color-theme-glow);
  opacity: 0.8;
}

.stat-value {
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.health-bar,
.happiness-bar {
  width: 100%;
  height: 10px;
  background: rgba(68, 68, 68, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 5px;
  overflow: hidden;
  margin-top: 0.25rem;
}

.health-fill,
.happiness-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-theme-primary) 0%, var(--color-theme-accent) 100%);
  box-shadow: 0 0 8px var(--color-theme-glow);
  transition: width 0.3s ease;
}

.inventory-stats {
  display: flex;
  gap: 1rem;
  justify-content: space-around;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  margin-top: 0.5rem;
}

.inventory-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.inventory-value {
  font-weight: 700;
  font-size: 1.125rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.inventory-label {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.actions-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

/* Item Actions */
.item-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.item-button {
  font-size: 0.875rem;
}

/* Coming Soon Section */
.coming-soon-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-theme-glow);
}

.locked-action-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.625rem 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.375rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: not-allowed;
  opacity: 0.5;
  transition: all 0.2s;
}

.locked-action-button:hover {
  background: rgba(0, 0, 0, 0.5);
  opacity: 0.75;
}

.locked-action-button .lock-icon {
  margin-left: auto;
}
</style>
