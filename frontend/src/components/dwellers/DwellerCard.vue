<script setup lang="ts">
import { computed, ref } from 'vue';
import { Icon } from '@iconify/vue';
import UButton from '@/components/ui/UButton.vue';
import UTooltip from '@/components/ui/UTooltip.vue';
import XPProgressBar from '@/components/dwellers/XPProgressBar.vue';
import { happinessService, type HappinessModifiers } from '@/services/happinessService';
import type { components } from '@/types/api.generated';
import type { VisualAttributes } from '@/models/dweller';

type DwellerDetailRead = components['schemas']['DwellerReadFull'];

interface Props {
  dweller: DwellerDetailRead;
  imageUrl?: string | null;
  loading?: boolean;
  generatingBio?: boolean;
  generatingPortrait?: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: 'chat'): void
  (e: 'assign'): void
  (e: 'recall'): void
  (e: 'generate-ai'): void
  (e: 'generate-bio'): void
  (e: 'generate-portrait'): void
  (e: 'train'): void
  (e: 'assign-pet'): void
  (e: 'use-stimpack'): void
  (e: 'use-radaway'): void
}>();

const showHappinessModifiers = ref(false);
const happinessModifiers = ref<HappinessModifiers | null>(null);
const loadingModifiers = ref(false);

const loadHappinessModifiers = async () => {
  if (happinessModifiers.value) {
    showHappinessModifiers.value = !showHappinessModifiers.value;
    return;
  }

  loadingModifiers.value = true;
  try {
    const response = await happinessService.getDwellerModifiers(props.dweller.id);
    happinessModifiers.value = response.data;
    showHappinessModifiers.value = true;
  } catch (error) {
    console.error('Failed to load happiness modifiers:', error);
  } finally {
    loadingModifiers.value = false;
  }
};

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

const happinessLevel = computed(() => {
  const happiness = props.dweller.happiness || 50;
  if (happiness >= 75) return 'high';
  if (happiness >= 50) return 'medium';
  if (happiness >= 25) return 'low';
  return 'critical';
});

const happinessColor = computed(() => {
  switch (happinessLevel.value) {
    case 'high': return 'var(--color-theme-primary)';
    case 'medium': return '#4ade80'; // green-400
    case 'low': return '#fbbf24'; // yellow-400
    case 'critical': return '#ef4444'; // red-500
    default: return 'var(--color-theme-primary)';
  }
});

const genderIcon = computed(() => {
  return props.dweller.gender === 'male' ? 'mdi:gender-male' : 'mdi:gender-female';
});

const genderColor = computed(() => {
  return props.dweller.gender === 'male' ? '#60a5fa' : '#f472b6'; // blue-400 : pink-400
});

const rarityColor = computed(() => {
  const rarity = props.dweller.rarity?.toLowerCase();
  switch (rarity) {
    case 'legendary': return '#fbbf24'; // yellow-400 (gold)
    case 'rare': return '#a78bfa'; // violet-400 (purple)
    case 'uncommon': return '#60a5fa'; // blue-400
    case 'common':
    default: return '#9ca3af'; // gray-400
  }
});

const rarityLabel = computed(() => {
  return props.dweller.rarity || 'Common';
});

// Visual attributes tooltip helper
const visualAttributesTooltip = computed(() => {
  const attrs = props.dweller.visual_attributes as VisualAttributes | null | undefined;
  if (!attrs) return null;

  const lines: string[] = [];
  const capitalize = (str: string) => str.charAt(0).toUpperCase() + str.slice(1);

  if (attrs.height) lines.push(`Height: ${capitalize(attrs.height)}`);
  if (attrs.hair_color || attrs.hair_style) {
    const hair = [attrs.hair_style, attrs.hair_color].filter((v): v is string => Boolean(v)).map(capitalize).join(', ');
    lines.push(`Hair: ${hair}`);
  }
  if (attrs.eye_color) lines.push(`Eyes: ${capitalize(attrs.eye_color)}`);
  if (attrs.build) lines.push(`Build: ${capitalize(attrs.build)}`);
  if (attrs.skin_tone) lines.push(`Skin: ${capitalize(attrs.skin_tone)}`);

  return lines.length > 0 ? lines.join('\n') : null;
});
</script>

<template>
  <div class="dweller-card">
    <!-- Portrait -->
    <div class="portrait-container">
      <template v-if="imageUrl">
        <UTooltip v-if="visualAttributesTooltip" :text="visualAttributesTooltip" position="right" :multiline="true">
          <img
            :src="getImageUrl(imageUrl)"
            alt="Dweller Portrait"
            class="portrait-image"
          />
        </UTooltip>
        <img
          v-else
          :src="getImageUrl(imageUrl)"
          alt="Dweller Portrait"
          class="portrait-image"
        />
      </template>
      <template v-else>
        <div class="portrait-placeholder">
          <Icon icon="mdi:account-circle" class="h-48 w-48" style="color: var(--color-theme-primary); opacity: 0.3;" />
        </div>

        <!-- Generate Portrait Button -->
        <UTooltip text="Generate AI portrait" position="right">
          <button
            @click="emit('generate-portrait')"
            class="ai-generate-button portrait-button"
            :disabled="generatingPortrait || loading"
          >
            <Icon
              :icon="generatingPortrait ? 'mdi:loading' : 'mdi:camera'"
              class="h-6 w-6"
              style="color: var(--color-theme-primary);"
              :class="{ 'animate-spin': generatingPortrait }"
            />
          </button>
        </UTooltip>

        <!-- Generate Full AI Button (both portrait and bio) -->
        <UTooltip text="Generate portrait & biography" position="right">
          <button
            @click="emit('generate-ai')"
            class="ai-generate-button full-generate-button"
            :disabled="loading"
          >
            <Icon
              :icon="loading ? 'mdi:loading' : 'mdi:sparkles'"
              class="h-6 w-6"
              style="color: var(--color-theme-primary);"
              :class="{ 'animate-spin': loading }"
            />
          </button>
        </UTooltip>
      </template>
    </div>

    <!-- Gender & Rarity Info -->
    <div class="info-badges">
      <div class="info-badge gender-badge" :style="{ borderColor: genderColor }">
        <Icon :icon="genderIcon" class="badge-icon" :style="{ color: genderColor }" />
        <span class="badge-text" :style="{ color: genderColor }">{{ dweller.gender }}</span>
      </div>
      <div class="info-badge rarity-badge" :style="{ borderColor: rarityColor }">
        <Icon icon="mdi:star" class="badge-icon" :style="{ color: rarityColor }" />
        <span class="badge-text" :style="{ color: rarityColor }">{{ rarityLabel }}</span>
      </div>
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

      <div class="stat-row happiness-row">
        <span class="stat-label">Happiness</span>
        <div class="happiness-value-container">
          <span class="stat-value" :style="{ color: happinessColor }">{{ dweller.happiness }}%</span>
          <button
            @click="loadHappinessModifiers"
            class="happiness-info-button"
            :disabled="loadingModifiers"
            title="View happiness modifiers"
          >
            <Icon
              :icon="loadingModifiers ? 'mdi:loading' : 'mdi:information-outline'"
              :class="{ 'animate-spin': loadingModifiers }"
              class="h-4 w-4"
              :style="{ color: happinessColor }"
            />
          </button>
        </div>
      </div>
      <div class="happiness-bar">
        <div class="happiness-fill" :style="{ width: `${dweller.happiness}%`, background: happinessColor }"></div>
      </div>

      <!-- Happiness Modifiers Dropdown -->
      <div v-if="showHappinessModifiers && happinessModifiers" class="happiness-modifiers">
        <div class="modifiers-header">
          <span class="modifiers-title">Happiness Modifiers</span>
          <button @click="showHappinessModifiers = false" class="close-button">
            <Icon icon="mdi:close" class="h-4 w-4" />
          </button>
        </div>

        <div v-if="happinessModifiers.positive.length > 0" class="modifiers-section">
          <div class="modifiers-label positive">Positive Effects</div>
          <div
            v-for="(modifier, index) in happinessModifiers.positive"
            :key="`pos-${index}`"
            class="modifier-item positive"
          >
            <Icon icon="mdi:arrow-up" class="modifier-icon" />
            <span class="modifier-name">{{ modifier.name }}</span>
            <span class="modifier-value">+{{ modifier.value.toFixed(1) }}</span>
          </div>
        </div>

        <div v-if="happinessModifiers.negative.length > 0" class="modifiers-section">
          <div class="modifiers-label negative">Negative Effects</div>
          <div
            v-for="(modifier, index) in happinessModifiers.negative"
            :key="`neg-${index}`"
            class="modifier-item negative"
          >
            <Icon icon="mdi:arrow-down" class="modifier-icon" />
            <span class="modifier-name">{{ modifier.name }}</span>
            <span class="modifier-value">{{ modifier.value.toFixed(1) }}</span>
          </div>
        </div>
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
        :disabled="loading"
      >
        <Icon icon="mdi:office-building" class="h-5 w-5 mr-2" />
        Assign to Room
      </UButton>

      <UButton
        v-if="props.dweller.status === 'exploring'"
        variant="secondary"
        size="md"
        block
        @click="emit('recall')"
        :disabled="loading"
      >
        <Icon icon="mdi:arrow-u-left-top" class="h-5 w-5 mr-2" />
        Recall from Wasteland
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
  background: rgba(31, 41, 55, 0.95);
  border: 2px solid var(--color-theme-glow);
  border-radius: 50%;
  padding: 0.75rem;
  cursor: pointer;
  transition: all 0.3s ease;
  animation: pulse-glow 2s ease-in-out infinite;
  z-index: 10;
}

.portrait-button {
  bottom: 1rem;
  right: 1rem;
}

.full-generate-button {
  top: 1rem;
  right: 1rem;
  padding: 1rem;
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

/* Info Badges */
.info-badges {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
  flex-wrap: wrap;
}

.info-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(0, 0, 0, 0.4);
  border: 2px solid;
  border-radius: 999px;
  font-family: 'Courier New', monospace;
  font-weight: 600;
  font-size: 0.875rem;
  text-transform: capitalize;
  box-shadow: 0 0 10px currentColor;
  transition: all 0.2s;
}

.info-badge:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 20px currentColor;
}

.badge-icon {
  font-size: 1.25rem;
  filter: drop-shadow(0 0 4px currentColor);
}

.badge-text {
  font-weight: 700;
  text-shadow: 0 0 8px currentColor;
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

.happiness-row {
  position: relative;
}

.happiness-value-container {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.happiness-info-button {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 50%;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.happiness-info-button:hover:not(:disabled) {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
  transform: scale(1.1);
}

.happiness-info-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

/* Happiness Modifiers */
.happiness-modifiers {
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  padding: 0.75rem;
  margin-top: 0.5rem;
  animation: slideDown 0.2s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modifiers-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.modifiers-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.close-button {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--color-theme-primary);
  padding: 0.25rem;
  border-radius: 50%;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-button:hover {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  transform: rotate(90deg);
}

.modifiers-section {
  margin-top: 0.5rem;
}

.modifiers-section:first-of-type {
  margin-top: 0;
}

.modifiers-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
  display: block;
}

.modifiers-label.positive {
  color: #4ade80;
}

.modifiers-label.negative {
  color: #ef4444;
}

.modifier-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  margin-bottom: 0.25rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  font-size: 0.8125rem;
  transition: all 0.2s;
}

.modifier-item:hover {
  background: rgba(0, 0, 0, 0.5);
  transform: translateX(2px);
}

.modifier-item.positive {
  border-left: 2px solid #4ade80;
}

.modifier-item.negative {
  border-left: 2px solid #ef4444;
}

.modifier-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.modifier-item.positive .modifier-icon {
  color: #4ade80;
}

.modifier-item.negative .modifier-icon {
  color: #ef4444;
}

.modifier-name {
  flex: 1;
  color: #e5e7eb;
}

.modifier-value {
  font-weight: 600;
  font-family: 'Courier New', monospace;
  flex-shrink: 0;
}

.modifier-item.positive .modifier-value {
  color: #4ade80;
}

.modifier-item.negative .modifier-value {
  color: #ef4444;
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
