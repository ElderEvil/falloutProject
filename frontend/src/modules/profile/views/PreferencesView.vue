<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useVisualEffects, type EffectIntensity } from '@/core/composables/useVisualEffects'
import { useTheme, type ThemeName } from '@/core/composables/useTheme'
import { useRoomRendering } from '@/core/composables/useRoomRendering'
import { useBadgeStyle } from '@/core/composables/useBadgeStyle'
import { audioManager, type AudioBus } from '@/core/audio/audioManager'
import { useProfileStore } from '../stores/profile'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useBackNavigation } from '@/core/composables/useBackNavigation'
import { handleStoreError } from '@/core/utils/errorHandler'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/core/components/ui/card'
import { Button } from '@/core/components/ui/button'
import { Switch } from '@/core/components/ui/switch'
import { Label } from '@/core/components/ui/label'
import { ToggleGroup, ToggleGroupItem } from '@/core/components/ui/toggle-group'
import { Slider } from '@/core/components/ui/slider'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'

const { isCollapsed } = useSidePanel()
const backNav = useBackNavigation('Preferences', () => '/profile')
const vaultStore = useVaultStore()
const {
  flickering,
  scanlines,
  glowIntensity,
  glowClass,
  prefersReducedMotion,
  toggleFlickering,
  toggleScanlines,
  setGlowIntensity,
  enableAllEffects,
  disableAllEffects,
  resetToDefaults,
} = useVisualEffects()

const { currentTheme, availableThemes, setTheme } = useTheme()
const { showRoomImages, toggleRoomImages } = useRoomRendering()
const { isMonochrome, toggleBadgeStyle } = useBadgeStyle()
const profileStore = useProfileStore()

const notificationCategories = [
  { key: 'exploration_updates', label: 'Exploration Updates', description: 'Routine events while a dweller explores' },
  { key: 'arrivals_and_completions', label: 'Arrivals & Completions', description: 'Exploration and quest party returns' },
  { key: 'advancement', label: 'Dweller Advancement', description: 'Level-ups and training progress' },
  { key: 'social_activity', label: 'Social Activity', description: 'Relationships, pregnancies, and births' },
  { key: 'crafting', label: 'Crafting', description: 'Crafting completion updates' },
  { key: 'vault_activity', label: 'Vault Activity', description: 'Radio arrivals and routine radio changes' },
] as const

const disabledNotificationCategories = computed(() => {
  const settings = profileStore.profile?.preferences?.notifications
  if (!settings || typeof settings !== 'object' || Array.isArray(settings)) return []
  const disabled = (settings as Record<string, unknown>).disabled_categories
  return Array.isArray(disabled) ? disabled.filter((category): category is string => typeof category === 'string') : []
})

// Optimistic selection: each toggle builds on the previous click's payload
// instead of the last confirmed server state, so rapid clicks cannot overwrite
// each other while a save is still in flight.
const pendingDisabledCategories = ref<Set<string> | null>(null)

const effectiveDisabledCategories = computed<string[]>(
  () => pendingDisabledCategories.value !== null ? [...pendingDisabledCategories.value] : disabledNotificationCategories.value,
)

const notificationCategoryEnabled = (category: string) => !effectiveDisabledCategories.value.includes(category)

const savingCategories = ref(new Set<string>())
const isSavingCategory = (category: string) => savingCategories.value.has(category)

const toggleNotificationCategory = (category: string, next?: boolean) => {
  const disabled = new Set(effectiveDisabledCategories.value)
  const shouldEnable = next ?? disabled.has(category)
  if (shouldEnable) disabled.delete(category)
  else disabled.add(category)
  const payload = [...disabled]
  pendingDisabledCategories.value = disabled
  savingCategories.value.add(category)
  void profileStore
    .savePreferences({ notifications: { version: 1, disabled_categories: payload } })
    .then(() => {
      // Keep later clicks: only drop the pending state if nothing changed since this save.
      const pending = pendingDisabledCategories.value
      if (pending !== null && pending.size === payload.length && payload.every((c) => pending.has(c)))
        pendingDisabledCategories.value = null
    })
    .catch((error: unknown) => {
      // Revert to the last confirmed server state so the toggle reflects reality.
      pendingDisabledCategories.value = null
      handleStoreError(error, 'Failed to save notification preferences')
    })
    .finally(() => {
      savingCategories.value.delete(category)
    })
}

const soundBusOptions: { bus: AudioBus; label: string; description: string }[] = [
  { bus: 'ui', label: 'Interface', description: 'Button clicks, tab switches, popups' },
  { bus: 'sfx', label: 'Game Effects', description: 'Incidents, completions, rewards' },
  { bus: 'music', label: 'Music', description: 'Vault ambient and exploration loops' },
]

const toggleSound = () => {
  audioManager.setMuted(!audioManager.muted)
  if (!audioManager.muted) audioManager.play('success', 'ui')
}

const setBusVolume = (bus: AudioBus, volume: number) => {
  audioManager.setVolume(bus, volume)
  // Audible feedback: play that bus's sample so the change is heard live.
  if (bus === 'music') audioManager.previewMusic()
  else audioManager.play(bus === 'sfx' ? 'success' : 'select', bus)
}

// Persist theme to the user profile so fetchProfile() does not reset the
// local choice back to the server-side preference on the next profile load.
const handleThemeChange = (themeName: ThemeName) => {
  setTheme(themeName)
  void profileStore.savePreferences({ theme: themeName }).catch((error: unknown) => {
    handleStoreError(error, 'Failed to save theme preference')
  })
}

// Get injected glow class from App.vue (with fallback)
const injectedGlowClass = inject('glowClass', glowClass)

const glowIntensityOptions: { value: EffectIntensity; label: string; description: string }[] = [
  { value: 'off', label: 'Off', description: 'No glow effects' },
  { value: 'subtle', label: 'Subtle', description: 'Minimal glow for readability' },
  { value: 'normal', label: 'Normal', description: 'Standard CRT glow' },
  { value: 'strong', label: 'Strong', description: 'Maximum retro aesthetics' },
]

const handleGlowSelect = (value: unknown) => {
  if (typeof value !== 'string') return
  const match = glowIntensityOptions.find((option) => option.value === value)
  if (match !== undefined) setGlowIntensity(match.value)
}
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-theme-primary [text-shadow:none]">
    <div class="vault-layout">
      <SidePanel :vault-id="vaultStore.activeVaultId" />

      <div class="main-content" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto px-4 py-6 lg:px-8">
          <div class="max-w-4xl mx-auto space-y-4">
            <PageHeader
              title="Preferences"
              icon="mdi:cog"
              subtitle="Customize terminal visuals, notification flow, and sound."
            >
              <template #back>
                <PageNavigation
                  :back-label="backNav.backLabel()"
                  :back-to="backNav.backTo()"
                  :breadcrumbs="backNav.breadcrumbs()"
                />
              </template>
            </PageHeader>

            <!-- Appearance -->
            <Card>
              <CardHeader>
                <CardTitle class="flex items-center gap-2 text-xl font-bold text-theme-primary">
                  <Icon icon="mdi:palette" class="text-xl" />
                  Appearance
                </CardTitle>
                <CardDescription>
                  Color theme, CRT effects, room artwork, and badge colors.
                </CardDescription>
              </CardHeader>
              <CardContent class="space-y-6">
                <div>
                  <h3 class="subsection-label">Color Theme</h3>
                  <p class="text-theme-primary/60 mb-3 text-xs">
                    Choose a color palette inspired by different Fallout games.
                  </p>

                  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <button
                      v-for="theme in availableThemes"
                      :key="theme.name"
                      @click="handleThemeChange(theme.name)"
                      class="theme-card"
                      :class="{ active: currentTheme.name === theme.name }"
                      :style="{
                        borderColor: theme.colors.primary,
                        boxShadow:
                          currentTheme.name === theme.name ? `0 0 15px ${theme.colors.glow}` : 'none',
                      }"
                      :aria-label="`Select ${theme.displayName}`"
                      :aria-pressed="currentTheme.name === theme.name"
                    >
                      <div
                        class="theme-preview"
                        :style="{ backgroundColor: theme.colors.primary }"
                      ></div>
                      <div class="theme-info">
                        <h4 class="theme-name" :style="{ color: theme.colors.primary }">
                          {{ theme.displayName }}
                        </h4>
                        <p class="theme-description">{{ theme.description }}</p>
                      </div>
                    </button>
                  </div>
                </div>

                <div>
                  <h3 class="subsection-label">CRT Visual Effects</h3>
                  <p class="text-theme-primary/60 mb-3 text-xs">
                    Configure retro terminal effects. Disable these for better accessibility or
                    performance.
                  </p>

                  <!-- Flickering Toggle -->
                  <Label class="setting-row cursor-pointer">
                    <div class="setting-info">
                      <div class="flex items-center gap-2">
                        <Icon
                          icon="mdi:flash"
                          class="text-xl text-theme-primary"
                        />
                        <h4 class="setting-label">Screen Flickering</h4>
                      </div>
                      <p class="setting-description">
                        Subtle animation that simulates old CRT monitors<span v-if="prefersReducedMotion"> — turned off because your system requests reduced motion</span>
                      </p>
                    </div>
                    <Switch
                      :checked="flickering"
                      :disabled="prefersReducedMotion"
                      :aria-label="prefersReducedMotion ? 'Screen flickering disabled by reduced-motion setting' : (flickering ? 'Disable flickering' : 'Enable flickering')"
                      @update:checked="() => toggleFlickering()"
                    />
                  </Label>

                  <!-- Scanlines Toggle -->
                  <Label class="setting-row cursor-pointer">
                    <div class="setting-info">
                      <div class="flex items-center gap-2">
                        <Icon
                          icon="mdi:view-sequential"
                          class="text-xl text-theme-primary"
                        />
                        <h4 class="setting-label">Scanlines</h4>
                      </div>
                      <p class="setting-description">
                        Horizontal line overlay for authentic terminal feel
                      </p>
                    </div>
                    <Switch
                      :checked="scanlines"
                      :aria-label="scanlines ? 'Disable scanlines' : 'Enable scanlines'"
                      @update:checked="() => toggleScanlines()"
                    />
                  </Label>

                  <!-- Glow Intensity -->
                  <div class="setting-row">
                    <div class="setting-info">
                      <div class="flex items-center gap-2">
                        <Icon
                          icon="mdi:lightbulb-on"
                          class="text-xl text-theme-primary"
                        />
                        <h4 class="setting-label">Text Glow Intensity</h4>
                      </div>
                      <p class="setting-description">Controls the brightness of text glow effects</p>
                      <!-- Live Demo -->
                      <div class="glow-demo mt-3">
                        <span class="demo-label">Preview: </span>
                        <span
                          :class="injectedGlowClass"
                          class="demo-text text-theme-primary"
                        >
                          VAULT-TEC TERMINAL
                        </span>
                      </div>
                      <!-- Glow Controls (moved inside setting-info) -->
                      <div class="glow-controls mt-3">
                        <TooltipProvider :delay-duration="200">
                          <ToggleGroup
                            type="single"
                            :model-value="glowIntensity"
                            :spacing="8"
                            class="glow-controls"
                            @update:model-value="handleGlowSelect"
                          >
                            <Tooltip v-for="option in glowIntensityOptions" :key="option.value">
                            <TooltipTrigger as-child>
                              <!-- @vue-ignore -->
                              <ToggleGroupItem
                                :value="option.value"
                                :aria-label="`Set glow to ${option.label}`"
                                class="glow-option"
                              >
                                  {{ option.label }}
                                </ToggleGroupItem>
                              </TooltipTrigger>
                              <TooltipContent side="top">{{ option.description }}</TooltipContent>
                            </Tooltip>
                          </ToggleGroup>
                        </TooltipProvider>
                      </div>
                    </div>
                  </div>

                  <div class="flex flex-wrap gap-3 pt-4">
                    <Button variant="outline" size="sm" @click="enableAllEffects">
                      <Icon icon="mdi:eye" class="mr-2" />
                      Enable All Effects
                    </Button>
                    <Button variant="outline" size="sm" @click="disableAllEffects">
                      <Icon icon="mdi:eye-off" class="mr-2" />
                      Disable All Effects
                    </Button>
                    <Button variant="outline" size="sm" @click="resetToDefaults">
                      <Icon icon="mdi:restore" class="mr-2" />
                      Reset Visual Effects
                    </Button>
                  </div>
                </div>

                <div class="setting-row">
                  <Label for="room-images" class="setting-info flex-col items-start cursor-pointer">
                    <span class="setting-label">Room Images</span>
                    <span class="setting-description">Show detailed vault artwork; turn off on slower devices.</span>
                  </Label>
                  <Switch
                    id="room-images"
                    :checked="showRoomImages"
                    @update:checked="() => toggleRoomImages()"
                  />
                </div>

                <div class="setting-row">
                  <Label for="colourful-badges" class="setting-info flex-col items-start cursor-pointer">
                    <span class="setting-label">Colourful Badges</span>
                    <span class="setting-description">Use category colours instead of one terminal tone.</span>
                  </Label>
                  <Switch
                    id="colourful-badges"
                    :checked="!isMonochrome"
                    @update:checked="() => toggleBadgeStyle()"
                  />
                </div>
              </CardContent>
            </Card>

            <!-- Notifications -->
            <Card>
              <CardHeader>
                <CardTitle class="flex items-center gap-2 text-xl font-bold text-theme-primary">
                  <Icon icon="mdi:bell-cog" class="text-xl" />
                  Notification Preferences
                </CardTitle>
                <CardDescription>
                  Turn off routine alerts you do not want to receive. Deaths, injuries, critical vault
                  alerts, exit requests, and combat failures always remain enabled.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Label
                  v-for="category in notificationCategories"
                  :key="category.key"
                  class="setting-row cursor-pointer"
                >
                  <div class="setting-info">
                    <h4 class="setting-label">{{ category.label }}</h4>
                    <p class="setting-description">{{ category.description }}</p>
                  </div>
                  <div class="flex items-center gap-2">
                    <span
                      v-if="isSavingCategory(category.key)"
                      aria-hidden="true"
                      class="inline-flex"
                    >
                      <Icon
                        icon="mdi:loading"
                        class="animate-spin text-sm text-theme-primary/50"
                      />
                    </span>
                    <Switch
                      :checked="notificationCategoryEnabled(category.key)"
                      :aria-label="notificationCategoryEnabled(category.key) ? `Disable ${category.label}` : `Enable ${category.label}`"
                      @update:checked="(next: boolean) => toggleNotificationCategory(category.key, next)"
                    />
                  </div>
                </Label>
              </CardContent>
            </Card>

            <!-- Sound -->
            <Card>
              <CardHeader>
                <CardTitle class="flex items-center gap-2 text-xl font-bold text-theme-primary">
                  <Icon icon="mdi:volume-high" class="text-xl" />
                  Sound
                </CardTitle>
                <CardDescription>
                  Sound is off by default. Enable it to add terminal feedback sounds and vault
                  ambience. Sound settings are stored on this device.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <!-- Master Enable -->
                <Label class="setting-row cursor-pointer">
                  <div class="setting-info">
                    <h4 class="setting-label">Sound Enabled</h4>
                    <p class="setting-description">Master switch for all game audio</p>
                  </div>
                  <Switch
                    :checked="audioManager.muted === false"
                    :aria-label="audioManager.muted ? 'Enable sound' : 'Disable sound'"
                    @update:checked="() => toggleSound()"
                  />
                </Label>

                <!-- Volume Sliders -->
                <template v-if="!audioManager.muted">
                  <div v-for="option in soundBusOptions" :key="option.bus" class="setting-row">
                    <div class="setting-info">
                      <h4 class="setting-label">{{ option.label }}</h4>
                      <p class="setting-description">{{ option.description }}</p>
                    </div>
                    <div class="w-40 shrink-0">
                      <!-- @vue-ignore -->
                      <Slider
                        :model-value="[audioManager.volumes[option.bus]]"
                        :min="0"
                        :max="1"
                        :step="0.05"
                        :aria-label="`${option.label} volume`"
                        @update:model-value="setBusVolume(option.bus, $event[0] ?? 0)"
                      />
                    </div>
                  </div>
                </template>
              </CardContent>
            </Card>
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
  font-weight: 700;
}

.main-content.collapsed {
  margin-left: 60px;
}

/* Subsection labels inside grouped cards */
.subsection-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-theme-accent);
  margin-bottom: 0.5rem;
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
  color: color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
  line-height: 1.2;
}

/* Settings Rows */
.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  padding: 1rem 0;
  border-bottom: 1px solid color-mix(in srgb, var(--color-theme-primary) 10%, transparent);
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
  color: color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
}

/* Glow Controls */
.glow-controls {
  display: flex;
  gap: 0.5rem;
}

:deep(.glow-option) {
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

:deep(.glow-option:hover) {
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

:deep(.glow-option[aria-pressed='true']) {
  background: var(--color-theme-primary);
  color: var(--color-terminal-background);
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
  color: color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
  text-transform: uppercase;
}

.demo-text {
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}

/* Volume sliders use the shared Slider component */

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
