<template>
  <div class="settings-view">
    <div class="settings-header">
      <h1 class="text-2xl font-bold">Game Balance Settings</h1>
      <p class="text-sm text-gray-400 mt-2">
        Current configuration values. These can be modified via environment variables on the server.
      </p>
    </div>

    <div v-if="loading" class="loading-state">
      <Icon icon="mdi:loading" class="loading-icon animate-spin" />
      <p class="mt-2">Loading settings...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <div v-else class="settings-content">
      <UTabs v-model="activeTab" :tabs="tabs" class="mb-6" />

      <!-- Game Loop -->
      <div v-show="activeTab === 'game-loop'" class="settings-section">
        <h2 class="section-title">Game Loop Configuration</h2>
        <UCard>
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
        </UCard>
      </div>

      <!-- Incidents -->
      <div v-show="activeTab === 'incidents'" class="settings-section">
        <h2 class="section-title">Incident System</h2>
        <UCard class="mb-4">
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
        </UCard>

        <h3 class="subsection-title">Spawn Weights</h3>
        <UCard class="mb-4">
          <SettingItem
            v-for="(weight, type) in settings.incident.spawn_weights"
            :key="type"
            :label="formatIncidentType(String(type))"
            :value="weight"
          />
        </UCard>

        <h3 class="subsection-title">Difficulty Ranges</h3>
        <UCard>
          <SettingItem
            v-for="(range, type) in settings.incident.difficulty_ranges"
            :key="type"
            :label="formatIncidentType(String(type))"
            :value="`${range[0]} - ${range[1]}`"
          />
        </UCard>
      </div>

      <!-- Combat -->
      <div v-show="activeTab === 'combat'" class="settings-section">
        <h2 class="section-title">Combat System</h2>
        <UCard class="mb-4">
          <SettingItem label="Base Raider Power" :value="settings.combat.base_raider_power" />
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
        </UCard>

        <h3 class="subsection-title">Loot</h3>
        <UCard class="mb-4">
          <SettingItem label="Base Caps Reward" :value="settings.combat.caps_reward_base" unit="caps" />
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
        </UCard>

        <h3 class="subsection-title">Experience</h3>
        <UCard>
          <SettingItem label="XP Per Difficulty" :value="settings.combat.xp_per_difficulty" unit="XP" />
          <SettingItem
            label="Perfect Bonus"
            :value="`${((settings.combat.perfect_bonus_multiplier - 1) * 100).toFixed(0)}%`"
            unit="extra"
          />
        </UCard>
      </div>

      <!-- Happiness -->
      <div v-show="activeTab === 'happiness'" class="settings-section">
        <h2 class="section-title">Happiness System</h2>
        <UCard class="mb-4">
          <h3 class="text-sm font-semibold mb-2">Decay Rates (per 60s tick)</h3>
          <SettingItem label="Base Decay" :value="settings.happiness.base_decay" :decimals="2" />
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
          <SettingItem label="Idle Decay" :value="settings.happiness.idle_decay" :decimals="2" />
        </UCard>

        <UCard class="mb-4">
          <h3 class="text-sm font-semibold mb-2">Gain Rates (per 60s tick)</h3>
          <SettingItem label="Working Gain" :value="settings.happiness.working_gain" :decimals="2" />
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
        </UCard>

        <UCard>
          <h3 class="text-sm font-semibold mb-2">Room Bonuses (per 60s tick)</h3>
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
        </UCard>
      </div>

      <!-- Training -->
      <div v-show="activeTab === 'training'" class="settings-section">
        <h2 class="section-title">Training System</h2>
        <UCard class="mb-4">
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
        </UCard>

        <h3 class="subsection-title">Tier Speed Multipliers</h3>
        <UCard>
          <SettingItem label="Tier 1 (Normal)" :value="settings.training.tier_1_multiplier" :decimals="2" />
          <SettingItem
            label="Tier 2"
            :value="`${settings.training.tier_2_multiplier} (${((1 - settings.training.tier_2_multiplier) * 100).toFixed(0)}% faster)`"
          />
          <SettingItem
            label="Tier 3"
            :value="`${settings.training.tier_3_multiplier} (${((1 - settings.training.tier_3_multiplier) * 100).toFixed(0)}% faster)`"
          />
        </UCard>
      </div>

      <!-- Resources -->
      <div v-show="activeTab === 'resources'" class="settings-section">
        <h2 class="section-title">Resource Management</h2>
        <UCard class="mb-4">
          <h3 class="text-sm font-semibold mb-2">Production</h3>
          <SettingItem
            label="Base Rate"
            :value="settings.resource.base_production_rate"
            :decimals="2"
            unit="per SPECIAL/sec"
          />
          <SettingItem label="Tier 1 Multiplier" :value="settings.resource.tier_1_multiplier" :decimals="2" />
          <SettingItem label="Tier 2 Multiplier" :value="settings.resource.tier_2_multiplier" :decimals="2" />
          <SettingItem label="Tier 3 Multiplier" :value="settings.resource.tier_3_multiplier" :decimals="2" />
        </UCard>

        <UCard class="mb-4">
          <h3 class="text-sm font-semibold mb-2">Consumption</h3>
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
        </UCard>

        <UCard>
          <h3 class="text-sm font-semibold mb-2">Warning Thresholds</h3>
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
        </UCard>
      </div>

      <!-- Leveling -->
      <div v-show="activeTab === 'leveling'" class="settings-section">
        <h2 class="section-title">Leveling System</h2>
        <UCard class="mb-4">
          <SettingItem label="Base XP Requirement" :value="settings.leveling.base_xp_requirement" unit="XP" />
          <SettingItem label="XP Curve Exponent" :value="settings.leveling.xp_curve_exponent" :decimals="2" />
          <SettingItem label="HP Per Level" :value="settings.leveling.hp_gain_per_level" unit="HP" />
          <SettingItem label="Max Level" :value="settings.leveling.max_level" />
        </UCard>

        <h3 class="subsection-title">Experience Sources</h3>
        <UCard>
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
        </UCard>
      </div>

      <!-- Relationships -->
      <div v-show="activeTab === 'relationships'" class="settings-section">
        <h2 class="section-title">Relationship System</h2>
        <UCard class="mb-4">
          <SettingItem
            label="Affinity Increase"
            :value="settings.relationship.affinity_increase_per_tick"
            unit="per tick"
          />
          <SettingItem label="Romance Threshold" :value="settings.relationship.romance_threshold" unit="affinity" />
          <SettingItem
            label="Partner Happiness Bonus"
            :value="settings.relationship.partner_happiness_bonus"
            unit="points"
          />
        </UCard>

        <h3 class="subsection-title">Compatibility Weights</h3>
        <UCard>
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
        </UCard>
      </div>

      <!-- Breeding -->
      <div v-show="activeTab === 'breeding'" class="settings-section">
        <h2 class="section-title">Breeding System</h2>
        <UCard>
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
            label="Child Growth Duration"
            :value="settings.breeding.child_growth_duration_hours"
            unit="hours"
          />
          <SettingItem
            label="Child SPECIAL Multiplier"
            :value="(settings.breeding.child_special_multiplier * 100).toFixed(0)"
            unit="%"
          />
        </UCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useToast } from '@/composables/useToast'
import apiClient from '@/plugins/axios'
import UCard from '@/components/ui/UCard.vue'
import UTabs from '@/components/ui/UTabs.vue'
import SettingItem from '@/components/SettingItem.vue'

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
  { key: 'breeding', label: 'Breeding' }
]

const settings = ref<any>({})
const loading = ref(true)
const error = ref<string | null>(null)

async function loadSettings() {
  try {
    const response = await apiClient.get('/api/v1/settings/game-balance')
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
.settings-view {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.settings-header {
  margin-bottom: 2rem;
}

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
  color: var(--color-primary);
}

.settings-content {
  margin-top: 1rem;
}

.settings-section {
  animation: fadeIn 0.3s ease-in;
}

.section-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--color-primary);
}

.subsection-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 1.5rem 0 0.75rem;
  color: var(--color-text-secondary);
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
