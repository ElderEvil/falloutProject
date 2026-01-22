<script setup lang="ts">
import { computed, inject, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useSidePanel } from '@/core/composables/useSidePanel';
import { useVisualEffects, type EffectIntensity } from '@/core/composables/useVisualEffects';
import { useTheme, type ThemeName } from '@/core/composables/useTheme';
import SidePanel from '@/core/components/common/SidePanel.vue';
import { UCard, UButton } from '@/core/components/ui';
import { Icon } from '@iconify/vue';

const router = useRouter();

const { isCollapsed } = useSidePanel();
const {
  flickering,
  scanlines,
  glowIntensity,
  glowClass,
  toggleFlickering,
  toggleScanlines,
  setGlowIntensity,
  enableAllEffects,
  disableAllEffects,
  resetToDefaults
} = useVisualEffects();

const { currentTheme, availableThemes, setTheme } = useTheme();

// Get injected glow class from App.vue (with fallback)
const injectedGlowClass = inject('glowClass', glowClass);

const glowIntensityOptions: { value: EffectIntensity; label: string; description: string }[] = [
  { value: 'off', label: 'Off', description: 'No glow effects' },
  { value: 'subtle', label: 'Subtle', description: 'Minimal glow for readability' },
  { value: 'normal', label: 'Normal', description: 'Standard CRT glow' },
  { value: 'strong', label: 'Strong', description: 'Maximum retro aesthetics' }
];
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines" v-if="scanlines"></div>

    <div class="vault-layout">
      <SidePanel />

      <div class="main-content" :class="{ collapsed: isCollapsed, flicker: flickering }">
        <div class="container mx-auto px-4 py-6 lg:px-8">
          <div class="max-w-4xl mx-auto">
<!-- Back Button -->
            <UButton variant="ghost" size="sm" class="mb-4" @click="router.push('/profile')">
              <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-1" />
              Back to Profile
            </UButton>

            <!-- Header -->
            <div class="mb-4">
              <h1 class="text-3xl font-bold flex items-center gap-2" :class="injectedGlowClass" :style="{ color: 'var(--color-theme-primary)' }">
                <Icon icon="mdi:cog" class="text-3xl" />
                Display Preferences
              </h1>
              <p class="text-gray-400 mt-1 text-sm">
                Customize the terminal visual effects and theme. All settings are saved locally.
              </p>
            </div>

            <!-- Theme Selection -->
            <UCard class="mb-4">
              <h2 class="text-xl font-bold mb-2 flex items-center gap-2" :style="{ color: 'var(--color-theme-primary)' }">
                <Icon icon="mdi:palette" class="text-xl" />
                Color Theme
              </h2>
              <p class="text-gray-400 mb-3 text-xs">
                Choose a color palette inspired by different Fallout games.
              </p>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button
                  v-for="theme in availableThemes"
                  :key="theme.name"
                  @click="setTheme(theme.name)"
                  class="theme-card"
                  :class="{ active: currentTheme.name === theme.name }"
                  :style="{
                    borderColor: theme.colors.primary,
                    boxShadow: currentTheme.name === theme.name ? `0 0 15px ${theme.colors.glow}` : 'none'
                  }"
                  :aria-label="`Select ${theme.displayName}`"
                >
                  <div class="theme-preview" :style="{ backgroundColor: theme.colors.primary }"></div>
                  <div class="theme-info">
                    <h3 class="theme-name" :style="{ color: theme.colors.primary }">{{ theme.displayName }}</h3>
                    <p class="theme-description">{{ theme.description }}</p>
                  </div>
                  <Icon
                    v-if="currentTheme.name === theme.name"
                    icon="mdi:check-circle"
                    class="check-icon"
                    :style="{ color: theme.colors.primary }"
                  />
                </button>
              </div>
            </UCard>

            <!-- Visual Effects -->
            <UCard class="mb-4">
              <h2 class="text-xl font-bold mb-2 flex items-center gap-2" :style="{ color: 'var(--color-theme-primary)' }">
                <Icon icon="mdi:television-classic" class="text-xl" />
                CRT Visual Effects
              </h2>
              <p class="text-gray-400 mb-3 text-xs">
                Configure retro terminal effects. Disable these for better accessibility or performance.
              </p>

              <!-- Flickering Toggle -->
              <div class="setting-row">
                <div class="setting-info">
                  <div class="flex items-center gap-2">
                    <Icon icon="mdi:flash" class="text-xl" :style="{ color: 'var(--color-theme-primary)' }" />
                    <h3 class="setting-label">Screen Flickering</h3>
                  </div>
                  <p class="setting-description">Subtle animation that simulates old CRT monitors</p>
                </div>
                <button
                  @click="toggleFlickering"
                  class="toggle-button"
                  :class="{ active: flickering }"
                  :aria-label="flickering ? 'Disable flickering' : 'Enable flickering'"
                >
                  <span class="toggle-slider"></span>
                </button>
              </div>

              <!-- Scanlines Toggle -->
              <div class="setting-row">
                <div class="setting-info">
                  <div class="flex items-center gap-2">
                    <Icon icon="mdi:view-sequential" class="text-xl" :style="{ color: 'var(--color-theme-primary)' }" />
                    <h3 class="setting-label">Scanlines</h3>
                  </div>
                  <p class="setting-description">Horizontal line overlay for authentic terminal feel</p>
                </div>
                <button
                  @click="toggleScanlines"
                  class="toggle-button"
                  :class="{ active: scanlines }"
                  :aria-label="scanlines ? 'Disable scanlines' : 'Enable scanlines'"
                >
                  <span class="toggle-slider"></span>
                </button>
              </div>

              <!-- Glow Intensity -->
              <div class="setting-row">
                <div class="setting-info">
                  <div class="flex items-center gap-2">
                    <Icon icon="mdi:lightbulb-on" class="text-xl" :style="{ color: 'var(--color-theme-primary)' }" />
                    <h3 class="setting-label">Text Glow Intensity</h3>
                  </div>
                  <p class="setting-description">Controls the brightness of text glow effects</p>
                  <!-- Live Demo -->
                  <div class="glow-demo mt-3">
                    <span class="demo-label">Preview: </span>
                    <span :class="injectedGlowClass" :style="{ color: 'var(--color-theme-primary)' }" class="demo-text">
                      VAULT-TEC TERMINAL
                    </span>
                  </div>
                  <!-- Glow Controls (moved inside setting-info) -->
                  <div class="glow-controls mt-3">
                    <button
                      v-for="option in glowIntensityOptions"
                      :key="option.value"
                      @click="setGlowIntensity(option.value)"
                      class="glow-option"
                      :class="{ active: glowIntensity === option.value }"
                      :aria-label="`Set glow to ${option.label}`"
                      :title="option.description"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                </div>
              </div>
            </UCard>

            <!-- Quick Actions -->
            <UCard>
              <h2 class="text-xl font-bold mb-2" :style="{ color: 'var(--color-theme-primary)' }">
                Quick Actions
              </h2>
              <div class="flex flex-wrap gap-3">
                <button
                  @click="enableAllEffects"
                  class="action-button"
                >
                  <Icon icon="mdi:eye" class="mr-2" />
                  Enable All Effects
                </button>
                <button
                  @click="disableAllEffects"
                  class="action-button"
                >
                  <Icon icon="mdi:eye-off" class="mr-2" />
                  Disable All Effects
                </button>
                <button
                  @click="resetToDefaults"
                  class="action-button"
                >
                  <Icon icon="mdi:restore" class="mr-2" />
                  Reset to Defaults
                </button>
              </div>
            </UCard>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
}

.main-content.collapsed {
  margin-left: 60px;
}

/* Theme Cards */
.theme-card {
  position: relative;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid;
  border-radius: 4px;
  transition: all 0.3s ease;
  text-align: left;
  cursor: pointer;
}

.theme-card:hover {
  background: rgba(0, 0, 0, 0.5);
}

.theme-card.active {
  background: rgba(0, 0, 0, 0.6);
  border-width: 3px;
}

.theme-preview {
  width: 100%;
  height: 30px;
  border-radius: 2px;
  margin-bottom: 0.5rem;
}

.theme-name {
  font-size: 0.95rem;
  font-weight: bold;
  margin-bottom: 0.125rem;
}

.theme-description {
  font-size: 0.75rem;
  color: var(--color-gray-400);
  line-height: 1.2;
}

.check-icon {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  font-size: 1.25rem;
}

/* Settings Rows */
.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid rgba(0, 255, 0, 0.1);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-info {
  flex: 1;
}

.setting-label {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  margin-bottom: 0.125rem;
}

.setting-description {
  font-size: 0.875rem;
  color: var(--color-gray-400);
}

/* Toggle Button */
.toggle-button {
  position: relative;
  width: 56px;
  height: 28px;
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid var(--color-theme-primary);
  border-radius: 14px;
  cursor: pointer;
  transition: background 0.3s ease;
}

.toggle-button.active {
  background: var(--color-theme-primary);
}

.toggle-slider {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: var(--color-theme-primary);
  border-radius: 50%;
  transition: transform 0.3s ease;
}

.toggle-button.active .toggle-slider {
  transform: translateX(28px);
  background: #000;
}

/* Glow Controls */
.glow-controls {
  display: flex;
  gap: 0.5rem;
}

.glow-option {
  padding: 0.5rem 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 0.875rem;
  font-weight: 600;
}

.glow-option:hover {
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.glow-option.active {
  background: var(--color-theme-primary);
  color: #000;
}

/* Glow Demo */
.glow-demo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
}

.demo-label {
  font-size: 0.75rem;
  color: var(--color-gray-400);
  text-transform: uppercase;
}

.demo-text {
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}

/* Action Buttons */
.action-button {
  display: flex;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-weight: 600;
}

.action-button:hover {
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.action-button:active {
  transform: scale(0.98);
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 0;
  }

  .main-content.collapsed {
    margin-left: 0;
  }

  .glow-controls {
    flex-direction: column;
    width: 100%;
  }

  .glow-option {
    width: 100%;
  }
}
</style>
