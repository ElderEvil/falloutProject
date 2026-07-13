<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useTheme } from '@/core/composables/useTheme'
import { useVisualEffects, type EffectIntensity } from '@/core/composables/useVisualEffects'
import SidePanel from '@/core/components/common/SidePanel.vue'
import UButton from '@/core/components/ui/UButton.vue'

const route = useRoute()
const router = useRouter()
const { isCollapsed } = useSidePanel()
const { currentTheme, setTheme, availableThemes } = useTheme()
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
  resetToDefaults,
} = useVisualEffects()

const vaultId = route.params.id as string

// Mock data for display
const activeExplorationsCount = 3
const activeQuestsCount = 2

const mockTabs = {
  activeTab: ref('daily'),
  questsTab: ref('active'),
}

const relationshipStages = [
  { id: 'forming', label: 'Forming', icon: 'mdi:account-group', count: 12 },
  { id: 'partners', label: 'Partners', icon: 'mdi:human-male-female', count: 5 },
  { id: 'pregnancies', label: 'Pregnancies', icon: 'mdi:baby-carriage', count: 2 },
  { id: 'children', label: 'Children', icon: 'mdi:human-child', count: 3 },
]

const mockStorage = {
  used: 42,
  max: 100,
  available: 58,
  pct: 42.0,
  stimpack: 15,
  radaway: 8,
}

const glowOptions: { value: EffectIntensity; label: string }[] = [
  { value: 'off', label: 'Off' },
  { value: 'subtle', label: 'Subtle' },
  { value: 'normal', label: 'Normal' },
  { value: 'strong', label: 'Strong' },
]

const activeTab = ref('daily')
const activeQuestTab = ref('active')
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono">
    <div class="scanlines" v-if="scanlines"></div>

    <div class="vault-layout">
      <SidePanel />

      <div class="main-content" :class="{ collapsed: isCollapsed, flicker: flickering }">
        <div class="container mx-auto px-4 py-6 lg:px-8">
          <!-- Back / Nav -->
          <UButton variant="ghost" size="sm" class="mb-4" @click="router.push(`/vault/${vaultId}`)">
            <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-1" />
            Back to Vault
          </UButton>

          <!-- Page Header -->
          <div class="mb-8">
            <h1
              class="text-3xl font-bold flex items-center gap-2 mb-1"
              :class="glowClass"
              :style="{ color: 'var(--color-theme-primary)' }"
            >
              <Icon icon="mdi:monitor-dashboard" class="text-3xl" />
              UI Component Test Page
            </h1>
            <p class="text-theme-accent text-sm">
              All sections below use CSS variables and effect classes. Switch themes or toggle
              effects to verify they propagate.
            </p>
          </div>

          <!-- Preference Controls -->
          <div
            class="controls-panel"
            :style="{
              borderColor: 'var(--color-theme-primary)',
              boxShadow: '0 0 15px var(--color-theme-glow)',
            }"
          >
            <!-- Theme Switcher -->
            <div class="control-section">
              <h3 class="control-label">
                <Icon icon="mdi:palette" class="mr-1" />
                Theme
              </h3>
              <div class="theme-chips">
                <button
                  v-for="theme in availableThemes"
                  :key="theme.name"
                  @click="setTheme(theme.name)"
                  class="theme-chip"
                  :class="{ active: currentTheme.name === theme.name }"
                  :style="{
                    borderColor: theme.colors.primary,
                    color: theme.colors.primary,
                    boxShadow:
                      currentTheme.name === theme.name ? `0 0 10px ${theme.colors.glow}` : 'none',
                  }"
                >
                  {{ theme.displayName }}
                </button>
              </div>
            </div>

            <!-- Effect Toggles -->
            <div class="control-section">
              <h3 class="control-label">
                <Icon icon="mdi:television-classic" class="mr-1" />
                Effects
              </h3>
              <div class="effect-toggles">
                <label class="toggle-row">
                  <span
                    class="toggle-label"
                    :style="{ color: flickering ? 'var(--color-theme-primary)' : '' }"
                    >Flicker</span
                  >
                  <button
                    class="toggle-btn"
                    :class="{ on: flickering }"
                    :style="{ borderColor: 'var(--color-theme-primary)' }"
                    @click="toggleFlickering"
                  >
                    <span class="toggle-dot" :class="{ on: flickering }" />
                  </button>
                </label>
                <label class="toggle-row">
                  <span
                    class="toggle-label"
                    :style="{ color: scanlines ? 'var(--color-theme-primary)' : '' }"
                    >Scanlines</span
                  >
                  <button
                    class="toggle-btn"
                    :class="{ on: scanlines }"
                    :style="{ borderColor: 'var(--color-theme-primary)' }"
                    @click="toggleScanlines"
                  >
                    <span class="toggle-dot" :class="{ on: scanlines }" />
                  </button>
                </label>
              </div>
            </div>

            <!-- Glow Intensity -->
            <div class="control-section">
              <h3 class="control-label">
                <Icon icon="mdi:lightbulb-on" class="mr-1" />
                Glow
              </h3>
              <div class="glow-chips">
                <button
                  v-for="opt in glowOptions"
                  :key="opt.value"
                  @click="setGlowIntensity(opt.value)"
                  class="glow-chip"
                  :class="{ active: glowIntensity === opt.value }"
                  :style="{ borderColor: 'var(--color-theme-primary)' }"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>

            <!-- Quick Actions -->
            <div class="control-section actions">
              <button
                class="action-btn"
                @click="enableAllEffects"
                :style="{
                  borderColor: 'var(--color-theme-primary)',
                  color: 'var(--color-theme-primary)',
                }"
              >
                <Icon icon="mdi:eye" /> All On
              </button>
              <button
                class="action-btn"
                @click="disableAllEffects"
                :style="{
                  borderColor: 'var(--color-theme-accent)',
                  color: 'var(--color-theme-accent)',
                }"
              >
                <Icon icon="mdi:eye-off" /> All Off
              </button>
              <button
                class="action-btn"
                @click="resetToDefaults"
                :style="{
                  borderColor: 'var(--color-theme-primary)',
                  color: 'var(--color-theme-primary)',
                }"
              >
                <Icon icon="mdi:restore" /> Reset
              </button>
            </div>
          </div>

          <!-- ===== SECTIONS GRID ===== -->
          <div class="sections-grid">
            <!-- 1. EXPLORATION -->
            <section
              class="section-card"
              :style="{
                borderColor: 'var(--color-theme-primary)',
                boxShadow: '0 0 12px var(--color-theme-glow)',
              }"
            >
              <div class="section-header-row">
                <div class="shrink-0">
                  <Icon
                    icon="mdi:compass"
                    class="section-icon"
                    :style="{ color: 'var(--color-theme-primary)' }"
                  />
                </div>
                <div class="section-header-text">
                  <h2 :class="glowClass" :style="{ color: 'var(--color-theme-primary)' }">
                    Wasteland Exploration
                  </h2>
                  <p class="section-subtitle">Monitor active explorations and quest parties</p>
                </div>
                <div class="stat-badges">
                  <div
                    class="stat-badge"
                    :style="{
                      borderColor: 'var(--color-theme-primary)',
                      background: 'rgba(0,0,0,0.3)',
                    }"
                  >
                    <Icon
                      icon="mdi:account-search"
                      :style="{ color: 'var(--color-theme-primary)' }"
                    />
                    <span class="stat-value" :style="{ color: 'var(--color-theme-primary)' }">{{
                      activeExplorationsCount
                    }}</span>
                    <span class="stat-label">Explorations</span>
                  </div>
                  <div
                    class="stat-badge"
                    :style="{
                      borderColor: 'var(--color-theme-primary)',
                      background: 'rgba(0,0,0,0.3)',
                    }"
                  >
                    <Icon icon="mdi:sword-cross" :style="{ color: 'var(--color-theme-primary)' }" />
                    <span class="stat-value" :style="{ color: 'var(--color-theme-primary)' }">{{
                      activeQuestsCount
                    }}</span>
                    <span class="stat-label">Quests</span>
                  </div>
                </div>
              </div>
            </section>

            <!-- 2. TRAINING -->
            <section
              class="section-card"
              :style="{
                borderColor: 'var(--color-theme-primary)',
                boxShadow: '0 0 12px var(--color-theme-glow)',
              }"
            >
              <div class="section-header-row">
                <Icon
                  icon="mdi:dumbbell"
                  class="section-icon"
                  :style="{ color: 'var(--color-theme-primary)' }"
                />
                <div class="section-header-text">
                  <h2 :class="glowClass" :style="{ color: 'var(--color-theme-primary)' }">
                    Training Center
                  </h2>
                  <p class="section-subtitle">
                    Monitor and manage SPECIAL stat training across your vault
                  </p>
                </div>
              </div>
            </section>

            <!-- 3. OBJECTIVES -->
            <section
              class="section-card"
              :style="{
                borderColor: 'var(--color-theme-primary)',
                boxShadow: '0 0 12px var(--color-theme-glow)',
              }"
            >
              <h2
                class="section-title-centered"
                :class="glowClass"
                :style="{ color: 'var(--color-theme-primary)' }"
              >
                Vault Objectives
              </h2>
              <div class="tab-bar" :style="{ borderBottomColor: 'var(--color-theme-glow)' }">
                <button
                  v-for="tab in ['daily', 'weekly', 'achievement', 'completed']"
                  :key="tab"
                  @click="activeTab = tab"
                  class="tab-btn"
                  :class="{ active: activeTab === tab }"
                  :style="{
                    color: 'var(--color-theme-primary)',
                    borderBottomColor:
                      activeTab === tab ? 'var(--color-theme-primary)' : 'transparent',
                    background: activeTab === tab ? 'var(--color-theme-glow)' : 'transparent',
                  }"
                >
                  {{ tab.charAt(0).toUpperCase() + tab.slice(1) }}
                </button>
              </div>
              <p class="section-hint" :style="{ color: 'var(--color-theme-accent)' }">
                {{
                  activeTab === 'daily'
                    ? '3 daily objectives available'
                    : activeTab === 'weekly'
                      ? '2 weekly objectives available'
                      : activeTab === 'achievement'
                        ? '1 achievement available'
                        : '5 completed objectives'
                }}
              </p>
            </section>

            <!-- 4. QUESTS -->
            <section
              class="section-card"
              :style="{
                borderColor: 'var(--color-theme-primary)',
                boxShadow: '0 0 12px var(--color-theme-glow)',
              }"
            >
              <h2
                class="section-title-centered"
                :class="glowClass"
                :style="{ color: 'var(--color-theme-primary)' }"
              >
                Vault Quests
              </h2>
              <div class="tab-bar" :style="{ borderBottomColor: 'var(--color-theme-glow)' }">
                <button
                  v-for="tab in ['active', 'completed']"
                  :key="tab"
                  @click="activeQuestTab = tab"
                  class="tab-btn"
                  :class="{ active: activeQuestTab === tab }"
                  :style="{
                    color: 'var(--color-theme-primary)',
                    borderBottomColor:
                      activeQuestTab === tab ? 'var(--color-theme-primary)' : 'transparent',
                    background: activeQuestTab === tab ? 'var(--color-theme-glow)' : 'transparent',
                  }"
                >
                  <Icon
                    :icon="tab === 'active' ? 'mdi:play-circle' : 'mdi:check-circle'"
                    class="mr-1"
                  />
                  {{ tab.charAt(0).toUpperCase() + tab.slice(1) }}
                </button>
              </div>
              <p class="section-hint" :style="{ color: 'var(--color-theme-accent)' }">
                {{
                  activeQuestTab === 'active'
                    ? '2 active quests, 4 available'
                    : '8 completed quests'
                }}
              </p>
            </section>

            <!-- 5. RELATIONSHIPS -->
            <section
              class="section-card"
              :style="{
                borderColor: 'var(--color-theme-primary)',
                boxShadow: '0 0 12px var(--color-theme-glow)',
              }"
            >
              <div class="section-header-row">
                <Icon
                  icon="mdi:heart-multiple"
                  class="section-icon"
                  :style="{ color: 'var(--color-theme-primary)' }"
                />
                <div class="section-header-text">
                  <h2 :class="glowClass" :style="{ color: 'var(--color-theme-primary)' }">
                    Relationships &amp; Family
                  </h2>
                  <p class="section-subtitle">
                    Manage relationships, pregnancies, and family growth
                  </p>
                </div>
              </div>

              <!-- Stats Grid (relationship style) -->
              <div class="stats-grid">
                <div
                  v-for="stage in relationshipStages"
                  :key="stage.id"
                  class="mini-stat-card"
                  :style="{
                    borderColor: 'var(--color-theme-glow)',
                    boxShadow: '0 0 8px var(--color-theme-glow)',
                  }"
                >
                  <Icon
                    :icon="stage.icon"
                    class="stat-card-icon"
                    :style="{ color: 'var(--color-theme-primary)' }"
                  />
                  <div class="stat-card-value" :style="{ color: 'var(--color-theme-primary)' }">
                    {{ stage.count }}
                  </div>
                  <div class="stat-card-label">{{ stage.label }}</div>
                </div>
              </div>

              <!-- Stage Tabs -->
              <div class="tab-bar" :style="{ borderBottomColor: 'var(--color-theme-glow)' }">
                <button
                  v-for="stage in relationshipStages"
                  :key="stage.id"
                  class="tab-btn stage-tab"
                  :style="{
                    color: 'var(--color-theme-primary)',
                    borderBottomColor: 'transparent',
                  }"
                >
                  {{ stage.label }}
                  <span
                    class="stage-count-badge"
                    :style="{ background: 'var(--color-theme-primary)', color: '#000' }"
                    >{{ stage.count }}</span
                  >
                </button>
              </div>
            </section>

            <!-- 6. HAPPINESS -->
            <section
              class="section-card"
              :style="{
                borderColor: 'var(--color-theme-primary)',
                boxShadow: '0 0 12px var(--color-theme-glow)',
              }"
            >
              <div class="section-header-row">
                <Icon
                  icon="mdi:emoticon-happy-outline"
                  class="section-icon"
                  :style="{ color: 'var(--color-theme-primary)' }"
                />
                <h2
                  class="section-title-glow"
                  :class="glowClass"
                  :style="{
                    color: 'var(--color-theme-primary)',
                    textShadow: '0 0 20px var(--color-theme-glow)',
                  }"
                >
                  VAULT HAPPINESS
                </h2>
              </div>
            </section>

            <!-- 7. STORAGE -->
            <section
              class="section-card"
              :style="{
                borderColor: 'var(--color-theme-primary)',
                boxShadow: '0 0 12px var(--color-theme-glow)',
              }"
            >
              <div class="section-header-row">
                <Icon
                  icon="mdi:package-variant"
                  class="section-icon"
                  :style="{ color: 'var(--color-theme-primary)' }"
                />
                <h2 :class="glowClass" :style="{ color: 'var(--color-theme-primary)' }">
                  Vault Storage
                </h2>
              </div>

              <!-- Storage Space Bar -->
              <div
                class="storage-card"
                :style="{
                  borderColor: 'var(--color-theme-primary)',
                  boxShadow: '0 0 10px var(--color-theme-glow)',
                }"
              >
                <div
                  class="flex items-center gap-2 mb-2 font-mono"
                  :style="{ color: 'var(--color-theme-accent)' }"
                >
                  <span class="text-sm font-semibold">Used:</span>
                  <span class="text-lg font-bold" :style="{ color: 'var(--color-theme-primary)' }"
                    >{{ mockStorage.used }}/{{ mockStorage.max }}</span
                  >
                </div>
                <div
                  class="progress-bar-track"
                  :style="{
                    borderColor: 'var(--color-theme-primary)',
                    background: 'rgba(0,0,0,0.5)',
                  }"
                >
                  <div
                    class="progress-bar-fill"
                    :style="{
                      width: `${mockStorage.pct}%`,
                      background: 'var(--color-theme-primary)',
                      boxShadow: '0 0 10px var(--color-theme-glow)',
                    }"
                  />
                </div>
                <div
                  class="text-xs text-center mt-1"
                  :style="{ color: 'var(--color-theme-accent)' }"
                >
                  {{ mockStorage.available }} slots available ({{ mockStorage.pct.toFixed(1) }}%
                  full)
                </div>
              </div>

              <!-- Medical Supplies -->
              <div
                class="storage-card"
                :style="{
                  borderColor: 'var(--color-theme-primary)',
                  boxShadow: '0 0 10px var(--color-theme-glow)',
                }"
              >
                <h3
                  class="text-sm font-semibold mb-3"
                  :style="{ color: 'var(--color-theme-accent)' }"
                >
                  Medical Supplies
                </h3>
                <div class="grid grid-cols-2 gap-3">
                  <div
                    class="med-item"
                    :style="{
                      borderColor: 'var(--color-theme-primary)',
                      background: 'rgba(0,0,0,0.3)',
                    }"
                  >
                    <Icon icon="mdi:medical-bag" class="w-6 h-6 text-green-500" />
                    <div>
                      <div class="font-bold" :style="{ color: 'var(--color-theme-primary)' }">
                        {{ mockStorage.stimpack }}
                      </div>
                      <div class="text-xs" :style="{ color: 'var(--color-theme-accent)' }">
                        Stimpaks
                      </div>
                    </div>
                  </div>
                  <div
                    class="med-item"
                    :style="{
                      borderColor: 'var(--color-theme-primary)',
                      background: 'rgba(0,0,0,0.3)',
                    }"
                  >
                    <Icon icon="mdi:pill" class="w-6 h-6 text-purple-500" />
                    <div>
                      <div class="font-bold" :style="{ color: 'var(--color-theme-primary)' }">
                        {{ mockStorage.radaway }}
                      </div>
                      <div class="text-xs" :style="{ color: 'var(--color-theme-accent)' }">
                        Radaways
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>
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
  margin-left: 64px;
}

/* Scanlines overlay */
.scanlines {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0) 50%, rgba(0, 255, 0, 0.02) 50%);
  background-size: 100% 4px;
  pointer-events: none;
  z-index: 1000;
}

/* --- Controls Panel --- */
.controls-panel {
  border: 2px solid;
  border-radius: 0.5rem;
  padding: 1rem;
  margin-bottom: 2rem;
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  align-items: flex-start;
  background: rgba(0, 0, 0, 0.3);
}

.control-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.control-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-accent);
  display: flex;
  align-items: center;
  font-weight: 600;
}

.theme-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.theme-chip {
  padding: 0.25rem 0.625rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  font-family: 'Courier New', monospace;
  cursor: pointer;
  transition: all 0.2s;
}

.theme-chip:hover {
  background: rgba(0, 0, 0, 0.5);
}

.theme-chip.active {
  background: rgba(0, 0, 0, 0.6);
  border-width: 3px;
}

.effect-toggles {
  display: flex;
  gap: 0.75rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.toggle-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-theme-accent);
}

.toggle-btn {
  position: relative;
  width: 40px;
  height: 20px;
  background: rgba(255, 255, 255, 0.08);
  border: 2px solid;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.3s;
  padding: 0;
}

.toggle-btn.on {
  background: var(--color-theme-primary);
}

.toggle-dot {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  background: var(--color-theme-primary);
  border-radius: 50%;
  transition: transform 0.3s;
}

.toggle-dot.on {
  transform: translateX(20px);
  background: #000;
}

.glow-chips {
  display: flex;
  gap: 0.25rem;
}

.glow-chip {
  padding: 0.25rem 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  font-family: 'Courier New', monospace;
  cursor: pointer;
  color: var(--color-theme-primary);
  transition: all 0.2s;
}

.glow-chip.active {
  background: var(--color-theme-primary);
  color: #000;
}

.actions {
  display: flex;
  flex-direction: row !important;
  align-items: center;
  gap: 0.5rem;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.375rem 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  font-family: 'Courier New', monospace;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(0, 0, 0, 0.5);
}

/* --- Sections Grid --- */
.sections-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}

@media (max-width: 1024px) {
  .sections-grid {
    grid-template-columns: 1fr;
  }
}

.section-card {
  border: 2px solid;
  border-radius: 0.5rem;
  padding: 1rem;
  background: transparent;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.section-header-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.section-icon {
  font-size: 1.75rem;
  filter: drop-shadow(0 0 6px var(--color-theme-glow));
  flex-shrink: 0;
}

.section-header-text {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  flex: 1;
}

.section-header-text h2 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.section-subtitle {
  margin: 0;
  font-size: 0.75rem;
  color: var(--color-theme-accent);
  opacity: 0.8;
}

.section-title-centered {
  font-size: 1.125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.section-title-glow {
  font-size: 1.125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.section-hint {
  font-size: 0.8rem;
  opacity: 0.8;
}

/* Stat Badges (Exploration style) */
.stat-badges {
  display: flex;
  gap: 0.75rem;
  flex-shrink: 0;
}

.stat-badge {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border: 2px solid;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

.stat-badge .stat-value {
  font-size: 1rem;
  font-weight: 700;
}

.stat-badge .stat-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.7;
  color: var(--color-theme-accent);
}

/* Tab Bar */
.tab-bar {
  display: flex;
  border-bottom: 2px solid;
  gap: 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.6;
  font-family: 'Courier New', monospace;
}

.tab-btn.active {
  opacity: 1;
}

.tab-btn:hover:not(.active) {
  opacity: 0.85;
  background: rgba(0, 0, 0, 0.15);
}

.stage-tab {
  font-size: 0.75rem;
  padding: 0.4rem 0.75rem;
}

.stage-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.25rem;
  height: 1.25rem;
  padding: 0 0.375rem;
  border-radius: 2px;
  font-size: 0.65rem;
  font-weight: 700;
  margin-left: 0.375rem;
}

/* Stats Grid (Relationship style) */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
}

@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.mini-stat-card {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.25);
  border: 2px solid;
  border-radius: 6px;
}

.stat-card-icon {
  font-size: 1.5rem;
  filter: drop-shadow(0 0 6px var(--color-theme-glow));
}

.stat-card-value {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1;
}

.stat-card-label {
  font-size: 0.65rem;
  color: var(--color-theme-accent);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* Storage Cards */
.storage-card {
  border: 2px solid;
  border-radius: 0.5rem;
  padding: 0.875rem;
  background: rgba(0, 0, 0, 0.2);
}

.progress-bar-track {
  width: 100%;
  height: 1.5rem;
  border: 2px solid;
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  transition: width 0.3s;
  border-radius: 2px;
}

.med-item {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.5rem;
  border: 1px solid;
  border-radius: 4px;
}

/* Flicker animation */
:global(.flicker) {
  animation: uiTestFlicker 0.15s infinite;
}

@keyframes uiTestFlicker {
  0% {
    opacity: 0.98;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.98;
  }
}
</style>
