<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UIconButton from '@/core/components/ui/UIconButton.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getCombatPower } from '@/modules/dwellers/models/dweller'
import type { Incident } from '../../models/incident'
import { getIncidentIcon, getTreatmentState, type VaultMedicalStocks } from '../../models/incident'

const props = defineProps<{
  incident: Incident
  dwellers: DwellerShort[]
  treatingDwellerId?: string | null
  vaultMedical?: VaultMedicalStocks
  preview?: boolean
}>()

const emit = defineEmits<{
  dwellerClick: [dwellerId: string]
  heal: [dwellerId: string]
  treatRadiation: [dwellerId: string]
}>()

const stocks = (): VaultMedicalStocks => props.vaultMedical ?? { stimpack: 0, radaway: 0 }
const heal = (dweller: DwellerShort) => getTreatmentState(dweller, stocks(), 'stimpack')
const rad = (dweller: DwellerShort) => getTreatmentState(dweller, stocks(), 'radaway')
const fullName = (dweller: DwellerShort) =>
  [dweller.first_name, dweller.last_name].filter(Boolean).join(' ')
const totalEnemies = computed(() => props.incident.progress.target)
const threatPoolPercent = computed(() =>
  totalEnemies.value > 0 ? Math.round((remainingEnemies.value / totalEnemies.value) * 100) : 0
)

const responders = computed(() => props.dwellers.filter((dweller) => dweller.room_id === props.incident.room_id))
const remainingEnemies = computed(() => Math.max(0, props.incident.progress.target - props.incident.progress.current))
const enemyIcons = computed(() => Array.from({ length: Math.min(5, remainingEnemies.value) }))
const progressPercent = computed(() =>
  props.incident.progress.target > 0
    ? Math.round((props.incident.progress.current / props.incident.progress.target) * 100)
    : 0
)
const latestEffect = computed(() => [...props.incident.events].reverse().find((event) => event.data !== null) ?? null)
const dwellerDamage = computed(() => Math.round(Number(latestEffect.value?.data?.damage_to_dwellers ?? 0)))
const threatDamage = computed(() => Math.round(Number(latestEffect.value?.data?.damage_to_threat ?? 0)))
const containmentGain = computed(() => Math.round(Number(latestEffect.value?.data?.amount ?? 0) * 100))
</script>

<template>
  <section class="incident-stage" :class="`incident-stage--${incident.family}`" aria-label="Incident live status">
    <div class="stage-side">
      <span class="stage-label">RESPONDERS</span>
      <div class="combatants effect-target">
        <span v-if="dwellerDamage" :key="latestEffect?.id" class="floating-effect floating-effect--damage">-{{ dwellerDamage }}</span>
        <div v-for="dweller in responders" :key="dweller.id" class="combatant">
          <button
            type="button"
            class="combatant-open"
            :title="`Open ${fullName(dweller)} details`"
            @click="emit('dwellerClick', dweller.id)"
          >
            <span class="combatant-portrait">{{ dweller.first_name[0] }}</span>
            <span class="combatant-name">{{ fullName(dweller) }}</span>
          </button>
          <span class="combatant-power">POW {{ getCombatPower(dweller) }}</span>
          <UProgressBar
            class="combatant-bar"
            :model-value="(dweller.health / dweller.max_health) * 100"
            :height="7"
            :glow="false"
          />
          <div class="combatant-actions">
            <UIconButton
              v-if="heal(dweller).need"
              icon="mdi:medical-bag"
              :label="preview ? 'Preview mode' : heal(dweller).title"
              :disabled="preview || treatingDwellerId != null"
              @click="emit('heal', dweller.id)"
            />
            <UIconButton
              v-if="rad(dweller).need"
              icon="mdi:radiation"
              :label="preview ? 'Preview mode' : rad(dweller).title"
              :disabled="preview || treatingDwellerId != null"
              @click="emit('treatRadiation', dweller.id)"
            />
          </div>
        </div>
        <span v-if="!responders.length" class="stage-empty">No responders assigned</span>
      </div>
    </div>

    <div class="stage-axis" aria-hidden="true">
      <Icon :icon="incident.objective === 'defeat' ? 'mdi:sword-cross' : 'mdi:arrow-right-bold'" />
    </div>

    <div v-if="incident.objective === 'defeat'" class="stage-side stage-side--threat">
      <span class="stage-label">THREAT</span>
      <div class="combatants combatants--enemies effect-target">
        <span v-if="threatDamage" :key="latestEffect?.id" class="floating-effect floating-effect--damage">-{{ threatDamage }}</span>
        <div class="threat-pool">
          <UProgressBar :model-value="threatPoolPercent" :height="8" :glow="false" color="var(--color-danger)" />
          <span class="enemy-count">{{ remainingEnemies }}/{{ totalEnemies }} left</span>
        </div>
        <div v-for="(_, index) in enemyIcons" :key="index" class="enemy-row">
          <Icon :icon="getIncidentIcon(incident.type)" class="enemy-icon" />
        </div>
      </div>
    </div>

    <div v-else class="stage-side stage-side--threat">
      <span class="stage-label">ROOM HAZARD</span>
      <div class="hazard-state effect-target">
        <span v-if="containmentGain" :key="latestEffect?.id" class="floating-effect floating-effect--containment">+{{ containmentGain }}%</span>
        <Icon :icon="getIncidentIcon(incident.type)" class="hazard-icon" />
        <div>
          <strong>{{ incident.progress.label }}</strong>
          <UProgressBar :model-value="progressPercent" :height="8" :glow="false" color="var(--color-warning)" />
          <span>{{ incident.risk.rooms_affected }} room{{ incident.risk.rooms_affected === 1 ? '' : 's' }} affected</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.incident-stage { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 1rem; padding: 1rem; border: 1px solid var(--color-surface-hover); background: var(--color-surface-sunken); }
.stage-side { min-width: 0; }
.stage-label { display: block; margin-bottom: .5rem; color: var(--color-theme-primary); font-size: .7rem; font-weight: 700; letter-spacing: .1em; }
.combatants { display: flex; flex-direction: column; align-items: stretch; gap: .4rem; }
.effect-target { position: relative; }
.floating-effect { position: absolute; top: -.9rem; z-index: 2; font-size: .85rem; font-weight: 700; animation: float-effect .9s ease-out both; }
.floating-effect--damage { color: var(--color-danger); }
.floating-effect--containment { color: var(--color-success); }
.combatant { display: flex; align-items: center; gap: .5rem; width: 100%; padding: .3rem .45rem; background: var(--color-surface-sunken); border: 1px solid var(--color-surface-hover); border-radius: 4px; color: var(--color-theme-primary); font-size: .75rem; }
.combatant-open { display: flex; align-items: center; gap: .5rem; flex: 0 1 9rem; min-width: 0; padding: 0; background: none; border: none; color: inherit; font: inherit; cursor: pointer; border-radius: 4px; }
.combatant-open:hover .combatant-name, .combatant-open:focus-visible .combatant-name { color: var(--color-warning); text-decoration: underline; }
.combatant-open:focus-visible { outline: 1px solid var(--color-theme-primary); outline-offset: 2px; }
.combatant-portrait { display: grid; place-items: center; width: 2rem; aspect-ratio: 1; flex: none; border: 1px solid var(--color-theme-primary); border-radius: 50%; font-size: .85rem; }
.combatant-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.combatant-power { color: var(--color-warning); font-size: .65rem; font-variant-numeric: tabular-nums; flex: none; min-width: 3.5rem; }
.combatant-bar { flex: 1 1 auto; min-width: 0; }
.combatant-actions { display: flex; justify-content: flex-end; gap: .25rem; flex: none; width: 3.75rem; }
.threat-pool { display: flex; flex-direction: column; gap: .25rem; }
.combatant-name, .stage-empty, .enemy-count, .hazard-state span { color: var(--color-theme-primary); opacity: .7; }
.stage-axis { display: grid; place-items: center; color: var(--color-danger); font-size: 1.5rem; }
.stage-side--threat { text-align: right; }
.combatants--enemies { align-items: flex-end; }
.enemy-row { display: flex; }
.enemy-icon, .hazard-icon { color: var(--color-danger); }
.enemy-icon { width: 1.25rem; height: 1.25rem; }
.hazard-state { display: flex; justify-content: flex-end; gap: .6rem; color: var(--color-warning); font-size: .7rem; text-align: left; }
.hazard-state > div { width: min(12rem, 100%); }
.hazard-icon { width: 2rem; height: 2rem; color: var(--color-warning); }
@media (max-width: 640px) { .incident-stage { grid-template-columns: 1fr; } .stage-axis { transform: rotate(90deg); } .stage-side--threat, .hazard-state { text-align: left; justify-content: flex-start; } .combatants--enemies { align-items: flex-start; } }
@keyframes float-effect { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-1.5rem); } }
</style>
