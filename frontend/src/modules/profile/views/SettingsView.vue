<template>
  <div
    class="relative min-h-screen bg-terminal-background font-mono text-theme-primary [text-shadow:none]"
  >
    <div class="flex min-h-screen">
      <SidePanel v-if="vaultStore.activeVaultId" :vault-id="vaultStore.activeVaultId" />
      <main
        class="min-w-0 flex-1 pb-8 transition-[margin-left] duration-300 ease max-md:ml-0"
        :class="vaultStore.activeVaultId ? (isCollapsed ? 'ml-16' : 'ml-60') : ''"
      >
        <PageContentRail>
          <PageHeader
            title="Game Balance Settings"
            subtitle="Current configuration values. These can be modified via environment variables on the server."
          >
            <template #back>
              <PageNavigation
                :back-label="backNav.backLabel()"
                :back-to="backNav.backTo()"
                :breadcrumbs="backNav.breadcrumbs()"
              />
            </template>
          </PageHeader>

          <div v-if="loading" class="loading-state">
            <Icon icon="mdi:loading" class="loading-icon animate-spin" />
            <p class="mt-2">Loading settings...</p>
          </div>

          <div v-else-if="error" class="error-state">
            <p class="text-red-500">{{ error }}</p>
          </div>

          <div v-else>
            <Tabs
              :model-value="activeTab"
              class="mb-6"
              @update:model-value="activeTab = String($event)"
            >
              <TabsList class="h-auto w-full flex-wrap justify-start gap-x-1 gap-y-2">
                <TabsTrigger v-for="tab in tabs" :key="tab.key" :value="tab.key">
                  {{ tab.label }}
                </TabsTrigger>
              </TabsList>
            </Tabs>

            <!-- Game Loop -->
            <div v-show="activeTab === 'game-loop'" class="settings-section">
              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary"
                    >Game Loop Configuration</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Tick Interval"
                    :value="settings.game_loop.tick_interval"
                    unit="seconds"
                  />
                  <SettingItem
                    label="Max Offline Catchup"
                    :value="settings.game_loop.max_offline_catchup"
                    unit="seconds"
                  />
                </CardContent>
              </Card>
            </div>

            <!-- Incidents -->
            <div v-show="activeTab === 'incidents'" class="settings-section">
              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary"
                    >Incident System</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Spawn Chance"
                    :value="(settings.incident.spawn_chance_per_hour * 100).toFixed(1)"
                    unit="% per hour"
                  />
                  <SettingItem
                    label="Min Population"
                    :value="settings.incident.min_vault_population"
                    unit="dwellers"
                  />
                  <SettingItem
                    label="Spread Duration"
                    :value="settings.incident.spread_duration"
                    unit="seconds"
                  />
                  <SettingItem
                    label="Max Spread Count"
                    :value="settings.incident.max_spread_count"
                    unit="spreads"
                  />
                </CardContent>
              </Card>

              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary"
                    >Spawn Weights</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    v-for="(weight, type) in settings.incident.spawn_weights"
                    :key="type"
                    :label="formatIncidentType(String(type))"
                    :value="weight"
                  />
                </CardContent>
              </Card>

              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary"
                    >Difficulty Ranges</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    v-for="(range, type) in settings.incident.difficulty_ranges"
                    :key="type"
                    :label="formatIncidentType(String(type))"
                    :value="`${range[0]} - ${range[1]}`"
                  />
                </CardContent>
              </Card>
            </div>

            <!-- Combat -->
            <div v-show="activeTab === 'combat'" class="settings-section">
              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary">Combat System</CardTitle>
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Base Raider Power"
                    :value="settings.combat.base_raider_power"
                  />
                  <SettingItem
                    label="Strength Weight"
                    :value="(settings.combat.dweller_strength_weight * 100).toFixed(0)"
                    unit="%"
                  />
                  <SettingItem
                    label="Endurance Weight"
                    :value="(settings.combat.dweller_endurance_weight * 100).toFixed(0)"
                    unit="%"
                  />
                  <SettingItem
                    label="Agility Weight"
                    :value="(settings.combat.dweller_agility_weight * 100).toFixed(0)"
                    unit="%"
                  />
                  <SettingItem
                    label="Level Bonus Multiplier"
                    :value="settings.combat.level_bonus_multiplier"
                  />
                </CardContent>
              </Card>

              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary">Loot</CardTitle>
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Base Caps Reward"
                    :value="settings.combat.caps_reward_base"
                    unit="caps"
                  />
                  <SettingItem
                    label="Caps Per Difficulty"
                    :value="settings.combat.caps_reward_per_difficulty"
                    unit="caps"
                  />
                  <SettingItem
                    label="Weapon Drop Chance"
                    :value="(settings.combat.weapon_drop_chance * 100).toFixed(1)"
                    unit="%"
                  />
                  <SettingItem
                    label="Outfit Drop Chance"
                    :value="(settings.combat.outfit_drop_chance * 100).toFixed(1)"
                    unit="%"
                  />
                  <SettingItem
                    label="Junk Drop Chance"
                    :value="(settings.combat.junk_drop_chance * 100).toFixed(1)"
                    unit="%"
                  />
                </CardContent>
              </Card>

              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary">Experience</CardTitle>
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="XP Per Difficulty"
                    :value="settings.combat.xp_per_difficulty"
                    unit="XP"
                  />
                  <SettingItem
                    label="Perfect Bonus"
                    :value="`${((settings.combat.perfect_bonus_multiplier - 1) * 100).toFixed(0)}%`"
                    unit="extra"
                  />
                </CardContent>
              </Card>
            </div>

            <!-- Happiness -->
            <div v-show="activeTab === 'happiness'" class="settings-section">
              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary">Decay Rates</CardTitle>
                  <CardDescription>Happiness change per 60-second tick</CardDescription>
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Base Decay"
                    :value="settings.happiness.base_decay"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Resource Shortage"
                    :value="settings.happiness.resource_shortage_decay"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Critical Resources"
                    :value="settings.happiness.critical_resource_decay"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Incident Penalty"
                    :value="settings.happiness.incident_penalty"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Idle Decay"
                    :value="settings.happiness.idle_decay"
                    :decimals="2"
                  />
                </CardContent>
              </Card>

              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary">Gain Rates</CardTitle>
                  <CardDescription>Happiness change per 60-second tick</CardDescription>
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Working Gain"
                    :value="settings.happiness.working_gain"
                    :decimals="2"
                  />
                  <SettingItem
                    label="High Health Bonus"
                    :value="settings.happiness.high_health_bonus"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Partner Nearby"
                    :value="settings.happiness.partner_nearby_bonus"
                    :decimals="2"
                  />
                </CardContent>
              </Card>

              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary"
                    >Room Bonuses</CardTitle
                  >
                  <CardDescription>Happiness change per 60-second tick</CardDescription>
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Living Quarters"
                    :value="settings.happiness.living_quarters_bonus"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Training Room"
                    :value="settings.happiness.training_room_bonus"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Radio Room"
                    :value="settings.happiness.radio_room_bonus"
                    :decimals="2"
                  />
                </CardContent>
              </Card>
            </div>

            <!-- Training -->
            <div v-show="activeTab === 'training'" class="settings-section">
              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary"
                    >Training System</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Base Duration"
                    :value="settings.training.base_duration_seconds / 3600"
                    :decimals="1"
                    unit="hours"
                  />
                  <SettingItem
                    label="Per Level Increase"
                    :value="settings.training.per_level_increase_seconds / 60"
                    :decimals="0"
                    unit="minutes"
                  />
                  <SettingItem label="Min SPECIAL" :value="settings.training.special_stat_min" />
                  <SettingItem label="Max SPECIAL" :value="settings.training.special_stat_max" />
                </CardContent>
              </Card>

              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary"
                    >Tier Speed Multipliers</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Tier 1 (Normal)"
                    :value="settings.training.tier_1_multiplier"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Tier 2"
                    :value="`${settings.training.tier_2_multiplier} (${((1 - settings.training.tier_2_multiplier) * 100).toFixed(0)}% faster)`"
                  />
                  <SettingItem
                    label="Tier 3"
                    :value="`${settings.training.tier_3_multiplier} (${((1 - settings.training.tier_3_multiplier) * 100).toFixed(0)}% faster)`"
                  />
                </CardContent>
              </Card>
            </div>

            <!-- Resources -->
            <div v-show="activeTab === 'resources'" class="settings-section">
              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary">Production</CardTitle>
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Base Rate"
                    :value="settings.resource.base_production_rate"
                    :decimals="2"
                    unit="per SPECIAL/sec"
                  />
                  <SettingItem
                    label="Tier 1 Multiplier"
                    :value="settings.resource.tier_1_multiplier"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Tier 2 Multiplier"
                    :value="settings.resource.tier_2_multiplier"
                    :decimals="2"
                  />
                  <SettingItem
                    label="Tier 3 Multiplier"
                    :value="settings.resource.tier_3_multiplier"
                    :decimals="2"
                  />
                </CardContent>
              </Card>

              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary"
                    >Consumption</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Power Rate"
                    :value="(settings.resource.power_consumption_rate * 60).toFixed(3)"
                    unit="per room/min"
                  />
                  <SettingItem
                    label="Food Per Dweller"
                    :value="(settings.resource.food_consumption_per_dweller * 60).toFixed(3)"
                    unit="per min"
                  />
                  <SettingItem
                    label="Water Per Dweller"
                    :value="(settings.resource.water_consumption_per_dweller * 60).toFixed(3)"
                    unit="per min"
                  />
                </CardContent>
              </Card>

              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary"
                    >Warning Thresholds</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Low Resource"
                    :value="(settings.resource.low_threshold * 100).toFixed(0)"
                    unit="%"
                  />
                  <SettingItem
                    label="Critical Resource"
                    :value="(settings.resource.critical_threshold * 100).toFixed(0)"
                    unit="%"
                  />
                </CardContent>
              </Card>
            </div>

            <!-- Leveling -->
            <div v-show="activeTab === 'leveling'" class="settings-section">
              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary"
                    >Leveling System</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Base XP Requirement"
                    :value="settings.leveling.base_xp_requirement"
                    unit="XP"
                  />
                  <SettingItem
                    label="XP Curve Exponent"
                    :value="settings.leveling.xp_curve_exponent"
                    :decimals="2"
                  />
                  <SettingItem
                    label="HP Per Level"
                    :value="settings.leveling.hp_gain_per_level"
                    unit="HP"
                  />
                  <SettingItem label="Max Level" :value="settings.leveling.max_level" />
                </CardContent>
              </Card>

              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary"
                    >Experience Sources</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Exploration (Per Mile)"
                    :value="settings.leveling.exploration_xp_per_distance"
                    unit="XP"
                  />
                  <SettingItem
                    label="Exploration (Per Enemy)"
                    :value="settings.leveling.exploration_xp_per_enemy"
                    unit="XP"
                  />
                  <SettingItem
                    label="Exploration (Per Event)"
                    :value="settings.leveling.exploration_xp_per_event"
                    unit="XP"
                  />
                  <SettingItem
                    label="Work (Per Tick)"
                    :value="settings.leveling.work_xp_per_tick"
                    unit="XP"
                  />
                </CardContent>
              </Card>
            </div>

            <!-- Relationships -->
            <div v-show="activeTab === 'relationships'" class="settings-section">
              <Card class="mb-4 gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary"
                    >Relationship System</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Affinity Increase"
                    :value="settings.relationship.affinity_increase_per_tick"
                    unit="per tick"
                  />
                  <SettingItem
                    label="Romance Threshold"
                    :value="settings.relationship.romance_threshold"
                    unit="affinity"
                  />
                  <SettingItem
                    label="Partner Happiness Bonus"
                    :value="settings.relationship.partner_happiness_bonus"
                    unit="points"
                  />
                </CardContent>
              </Card>

              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-lg font-semibold text-theme-primary"
                    >Compatibility Weights</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="SPECIAL Similarity"
                    :value="(settings.relationship.compatibility_special_weight * 100).toFixed(0)"
                    unit="%"
                  />
                  <SettingItem
                    label="Happiness"
                    :value="(settings.relationship.compatibility_happiness_weight * 100).toFixed(0)"
                    unit="%"
                  />
                  <SettingItem
                    label="Level Similarity"
                    :value="(settings.relationship.compatibility_level_weight * 100).toFixed(0)"
                    unit="%"
                  />
                  <SettingItem
                    label="Proximity"
                    :value="(settings.relationship.compatibility_proximity_weight * 100).toFixed(0)"
                    unit="%"
                  />
                </CardContent>
              </Card>
            </div>

            <!-- Breeding -->
            <div v-show="activeTab === 'breeding'" class="settings-section">
              <Card class="gap-0">
                <CardHeader>
                  <CardTitle class="text-xl font-bold text-theme-primary"
                    >Breeding System</CardTitle
                  >
                </CardHeader>
                <CardContent class="px-0">
                  <SettingItem
                    label="Conception Chance"
                    :value="(settings.breeding.conception_chance_per_tick * 100).toFixed(1)"
                    unit="% per tick"
                  />
                  <SettingItem
                    label="Pregnancy Duration"
                    :value="settings.breeding.pregnancy_duration_hours"
                    unit="hours"
                  />
                  <SettingItem
                    label="Trait Variance"
                    :value="`± ${settings.breeding.trait_inheritance_variance}`"
                    unit="SPECIAL"
                  />
                  <SettingItem
                    label="Rarity Upgrade Chance"
                    :value="(settings.breeding.rarity_upgrade_chance * 100).toFixed(0)"
                    unit="%"
                  />
                  <SettingItem
                    label="Time to Adulthood"
                    :value="settings.breeding.child_growth_duration_hours"
                    unit="hours"
                  />
                  <SettingItem
                    label="Child SPECIAL Multiplier"
                    :value="(settings.breeding.child_special_multiplier * 100).toFixed(0)"
                    unit="%"
                  />
                </CardContent>
              </Card>
            </div>
          </div>
        </PageContentRail>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useToast } from '@/core/composables/useToast'
import { useBackNavigation } from '@/core/composables/useBackNavigation'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useVaultStore } from '@/modules/vault/stores/vault'
import apiClient from '@/core/plugins/axios'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import SettingItem from '@/core/components/ui/SettingItem.vue'

const vaultStore = useVaultStore()
const backNav = useBackNavigation('Settings', () =>
  vaultStore.activeVaultId ? `/vault/${vaultStore.activeVaultId}` : '/'
)
const { isCollapsed } = useSidePanel()

const { error: showError } = useToast()

const activeTab = ref('game-loop')
const tabs = [
  { key: 'game-loop', label: 'Game Loop' },
  { key: 'incidents', label: 'Incidents' },
  { key: 'combat', label: 'Combat' },
  { key: 'happiness', label: 'Happiness' },
  { key: 'training', label: 'Training' },
  { key: 'resources', label: 'Resources' },
  { key: 'leveling', label: 'Leveling' },
  { key: 'relationships', label: 'Relationships' },
  { key: 'breeding', label: 'Breeding' },
]

const settings = ref<any>({})
const loading = ref(true)
const error = ref<string | null>(null)

async function loadSettings() {
  try {
    const response = await apiClient.get('/api/v1/game/balance')
    settings.value = response.data
  } catch (err) {
    error.value = 'Failed to load game balance settings'
    showError('Failed to load game balance settings')
  } finally {
    loading.value = false
  }
}

function formatIncidentType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.loading-icon {
  font-size: 3rem;
  color: var(--color-theme-primary);
}

.settings-section {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
