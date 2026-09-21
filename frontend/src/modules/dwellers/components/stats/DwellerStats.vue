<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { Dweller } from '../../models/dweller'
import { describeBonusSources, getSpecialBreakdown } from '../../models/specialBreakdown'
import { useDwellerDetailContext } from '../DwellerDetailContext'

const ctx = useDwellerDetailContext()

type StatKey = {
  [Key in keyof Dweller]-?: Dweller[Key] extends number ? Key : never
}[keyof Dweller]

const statValue = (key: StatKey): number => {
  const d = ctx.dweller.value
  if (!d) return 0
  const raw = d[key]
  return typeof raw === 'number' ? raw : 0
}

const stats: Array<{ key: StatKey; label: string; description: string }> = [
  { key: 'S', label: 'Strength', description: 'Physical power and melee damage' },
  { key: 'P', label: 'Perception', description: 'Accuracy and awareness' },
  { key: 'E', label: 'Endurance', description: 'Health and radiation resistance' },
  { key: 'C', label: 'Charisma', description: 'Trading and breeding success' },
  { key: 'I', label: 'Intelligence', description: 'Crafting and science efficiency' },
  { key: 'A', label: 'Agility', description: 'Speed and weapon reload' },
  { key: 'L', label: 'Luck', description: 'Critical hits and loot quality' },
]

const statKeyByLowercase = stats.reduce<Record<string, StatKey>>((acc, stat) => {
  acc[stat.label.toLowerCase()] = stat.key
  return acc
}, {})

/**
 * Base vs effective per stat (stored + identity + outfit, floored at 1, uncapped).
 * Shared breakdown helper so every surface explains bonuses identically.
 */
const breakdowns = computed(() => getSpecialBreakdown(ctx.dweller.value))

const breakdownByKey = computed(() => {
  const map = new Map<string, (typeof breakdowns.value)[number]>()
  for (const row of breakdowns.value) map.set(row.letter, row)
  return map
})

const effectiveValue = (key: StatKey): number => breakdownByKey.value.get(key)?.effective ?? statValue(key)

const bonusSources = (key: StatKey): string[] => {
  const row = breakdownByKey.value.get(key)
  return row ? describeBonusSources(row) : []
}

const highlightedKey = computed<StatKey | undefined>(() => {
  const highlighted = ctx.highlightStat.value
  if (!highlighted) return undefined
  return statKeyByLowercase[highlighted.toLowerCase()]
})

const showBadge = ref(!!highlightedKey.value)
let badgeTimer: ReturnType<typeof setTimeout> | undefined

watch(
  highlightedKey,
  (stat) => {
    clearTimeout(badgeTimer)
    showBadge.value = !!stat
    if (stat) badgeTimer = setTimeout(() => (showBadge.value = false), 2500)
  },
  { immediate: true }
)
onBeforeUnmount(() => clearTimeout(badgeTimer))

const isHighlighted = (key: StatKey) => highlightedKey.value === key

const STAT_MODIFIER_FIELDS = stats.map(({ label }) => ({ field: label.toLowerCase(), label }))

/**
 * Race/faction effects, computed server-side. Rendering them here answers
 * "why is this dweller effective" without the client re-deriving the rules.
 */
const modifierRows = computed<Array<{ label: string; value: string; icon: string }>>(() => {
  const modifiers = ctx.dweller.value?.identity_modifiers
  if (!modifiers) return []

  const rows = STAT_MODIFIER_FIELDS.flatMap(({ field, label }) => {
    const delta = modifiers[field as keyof typeof modifiers]
    if (typeof delta !== 'number' || delta === 0) return []
    return [
      {
        label,
        value: `${delta > 0 ? '+' : ''}${delta}`,
        icon: delta > 0 ? 'mdi:chevron-up' : 'mdi:chevron-down',
      },
    ]
  })

  const percent = (share: number) => `${Math.round(share * 100)}%`
  if (modifiers.radiation_immune) {
    rows.push({ label: 'Radiation', value: 'Immune', icon: 'mdi:radiation' })
  } else if (modifiers.radiation_resist_pct > 0) {
    rows.push({ label: 'Radiation Resist', value: percent(modifiers.radiation_resist_pct), icon: 'mdi:radiation' })
  }
  if (modifiers.energy_weapon_damage_pct > 0) {
    rows.push({ label: 'Energy Weapons', value: percent(modifiers.energy_weapon_damage_pct), icon: 'mdi:lightning-bolt' })
  }
  if (modifiers.melee_damage_pct > 0) {
    rows.push({ label: 'Melee', value: percent(modifiers.melee_damage_pct), icon: 'mdi:sword' })
  }
  if (modifiers.incident_response_pct > 0) {
    rows.push({ label: 'Incident Response', value: `-${percent(modifiers.incident_response_pct)} damage`, icon: 'mdi:shield-half-full' })
  }
  if (modifiers.production_pct > 0) {
    rows.push({ label: 'Production', value: percent(modifiers.production_pct), icon: 'mdi:factory' })
  }
  return rows
})
</script>

<template>
  <div class="dweller-stats">
    <div class="panel-header">
      <h3 class="stats-title panel-title">S.P.E.C.I.A.L.</h3>
    </div>
    <div class="stats-grid">
      <div
        v-for="stat in stats"
        :key="stat.key"
        class="stat-item"
        :class="{ 'stat-highlighted stat-highlight-pulse': isHighlighted(stat.key) }"
      >
        <div class="stat-header">
          <span class="stat-label">{{ stat.label }}</span>
          <span class="stat-value-group">
            <span class="stat-value">{{ effectiveValue(stat.key) }}</span>
            <span v-if="isHighlighted(stat.key) && showBadge" class="stat-badge stat-badge-fade"
              >+1</span
            >
          </span>
        </div>
        <div class="stat-bar">
          <div class="stat-fill" :style="{ width: `${Math.min(100, effectiveValue(stat.key) * 10)}%` }"></div>
        </div>
        <p v-if="bonusSources(stat.key).length > 0" class="stat-breakdown">
          {{ statValue(stat.key) }} → {{ effectiveValue(stat.key) }} ({{ bonusSources(stat.key).join(' · ') }})
        </p>
        <p class="stat-description">{{ stat.description }}</p>
      </div>
    </div>

    <div v-if="modifierRows.length > 0" class="identity-modifiers">
      <h4 class="modifiers-title">Identity Bonuses</h4>
      <div class="modifiers-grid">
        <div v-for="row in modifierRows" :key="row.label" class="modifier-row">
          <Icon :icon="row.icon" class="modifier-icon" />
          <span class="modifier-label">{{ row.label }}</span>
          <span class="modifier-value">{{ row.value }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.identity-modifiers {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-theme-glow);
}

.modifiers-title {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-theme-primary);
  opacity: 0.7;
  margin-bottom: 0.5rem;
}

.modifiers-grid {
  display: grid;
  gap: 0.25rem;
}

.modifier-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: var(--color-theme-primary);
}

.modifier-icon {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  opacity: 0.8;
}

.modifier-label {
  opacity: 0.75;
}

.modifier-value {
  margin-left: auto;
  font-weight: 700;
}

.dweller-stats {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.stats-grid {
  display: grid;
  gap: 0.5rem;
}

.stat-item {
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border-left: 2px solid var(--color-theme-glow);
  border-radius: 4px;
  transition: all 0.2s ease;
}

.stat-item:hover {
  background: rgba(0, 0, 0, 0.5);
  border-left-color: var(--color-theme-primary);
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-weight: 600;
  font-size: 0.8125rem;
  color: var(--color-theme-primary);
}

.stat-value {
  font-weight: 700;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  min-width: 1.5rem;
  text-align: right;
}

.stat-bar {
  position: relative;
  width: 100%;
  height: 8px;
  background: rgba(68, 68, 68, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.stat-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: var(--color-theme-primary);
  transition: width 0.3s ease;
}

.stat-description {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
  line-height: 1.3;
}

.stat-breakdown {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-theme-accent);
  line-height: 1.3;
  margin-bottom: 0.25rem;
}

.stat-value-group {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
}

.stat-badge {
  font-size: 0.6875rem;
  font-weight: 700;
  color: var(--color-theme-accent);
}

.stat-highlighted {
  border-left-color: var(--color-theme-accent);
  background: color-mix(in srgb, var(--color-theme-primary) 6%, transparent);
}
</style>
