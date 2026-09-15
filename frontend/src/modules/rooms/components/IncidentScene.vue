<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getCombatPower } from '@/modules/dwellers/models/dweller'
import type { Incident } from '@/modules/combat/models/incident'
import { getIncidentIcon } from '@/modules/combat/models/incident'

const props = defineProps<{
  incident: Incident
  dwellers: DwellerShort[]
  roomImageUrl?: string | null
}>()

const responders = computed(() =>
  props.dwellers.filter((dweller) => dweller.room_id === props.incident.room_id)
)
const remainingEnemies = computed(() =>
  Math.max(0, props.incident.progress.target - props.incident.progress.current)
)
const enemyIcons = computed(() => Array.from({ length: Math.min(5, remainingEnemies.value) }))
const progressPercent = computed(() =>
  props.incident.progress.target > 0
    ? Math.round((props.incident.progress.current / props.incident.progress.target) * 100)
    : 0
)
const latestEffect = computed(
  () => [...props.incident.events].reverse().find((event) => event.data !== null) ?? null
)
const dwellerDamage = computed(() => Number(latestEffect.value?.data?.damage_to_dwellers ?? 0))
const threatDamage = computed(() => Number(latestEffect.value?.data?.damage_to_threat ?? 0))
const containmentGain = computed(() => Math.round(Number(latestEffect.value?.data?.amount ?? 0) * 100))
</script>

<template>
  <section
    class="incident-scene"
    :class="`incident-scene--${incident.family}`"
    aria-label="Incident live status"
  >
    <div
      v-if="roomImageUrl"
      class="scene-backdrop"
      :style="{ backgroundImage: `url(${roomImageUrl})` }"
      aria-hidden="true"
    ></div>

    <div class="stage-side">
      <span class="stage-label">RESPONDERS</span>
      <div class="combatants effect-target">
        <span
          v-if="dwellerDamage"
          :key="latestEffect?.id"
          class="floating-effect floating-effect--damage"
        >
          -{{ dwellerDamage }}
        </span>
        <div v-for="dweller in responders" :key="dweller.id" class="combatant">
          <span class="combatant-portrait">{{ dweller.first_name[0] }}</span>
          <span class="combatant-name">{{ dweller.first_name }}</span>
          <span class="combatant-power">POW {{ getCombatPower(dweller) }}</span>
          <UProgressBar
            :model-value="(dweller.health / dweller.max_health) * 100"
            :height="7"
            :glow="false"
          />
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
        <span
          v-if="threatDamage"
          :key="latestEffect?.id"
          class="floating-effect floating-effect--damage"
        >
          -{{ threatDamage }}
        </span>
        <Icon
          v-for="(_, index) in enemyIcons"
          :key="index"
          :icon="getIncidentIcon(incident.type)"
          class="enemy-icon"
        />
        <span class="enemy-count">{{ remainingEnemies }} remaining</span>
      </div>
    </div>

    <div v-else class="stage-side stage-side--threat">
      <span class="stage-label">ROOM HAZARD</span>
      <div class="hazard-state effect-target">
        <span
          v-if="containmentGain"
          :key="latestEffect?.id"
          class="floating-effect floating-effect--containment"
        >
          +{{ containmentGain }}%
        </span>
        <svg
          v-if="incident.type === 'fire'"
          class="hazard-flame"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            class="flame-outer"
            d="M12 2.5c2.5 3.5 5.5 5.8 5.5 9.6a5.5 5.5 0 0 1-11 0c0-2 1-3.6 2.3-5.2.6 1 1.2 1.6 2 2 .3-2.3.7-4.2 1.2-6.4Z"
          />
          <path
            class="flame-inner"
            d="M12 9c1.2 1.6 2.3 2.8 2.3 4.5a2.3 2.3 0 0 1-4.6 0c0-1.7 1.1-2.9 2.3-4.5Z"
          />
        </svg>
        <Icon v-else :icon="getIncidentIcon(incident.type)" class="hazard-icon" />
        <div>
          <strong>{{ incident.progress.label }}</strong>
          <UProgressBar
            :model-value="progressPercent"
            :height="8"
            :glow="false"
            color="var(--color-warning)"
          />
          <span
            >{{ incident.risk.rooms_affected }} room{{
              incident.risk.rooms_affected === 1 ? '' : 's'
            }}
            affected</span
          >
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.incident-scene {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--color-surface-hover);
  background: var(--color-surface-sunken);
  overflow: hidden;
}

.scene-backdrop {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0.18;
}
.stage-side {
  position: relative;
  min-width: 0;
}
.stage-label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--color-theme-primary);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
}
.combatants {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.effect-target {
  position: relative;
}
.floating-effect {
  position: absolute;
  top: -0.9rem;
  z-index: 2;
  font-size: 0.85rem;
  font-weight: 700;
  animation: float-effect 0.9s ease-out both;
}
.floating-effect--damage {
  color: var(--color-danger);
}
.floating-effect--containment {
  color: var(--color-success);
}
.combatant {
  display: grid;
  grid-template-columns: 2rem minmax(0, 1fr);
  gap: 0.15rem 0.5rem;
  align-items: center;
  min-width: 7rem;
  color: var(--color-theme-primary);
  font-size: 0.75rem;
}
.combatant-portrait {
  grid-row: span 3;
  display: grid;
  place-items: center;
  width: 2rem;
  aspect-ratio: 1;
  border: 1px solid var(--color-theme-primary);
  border-radius: 50%;
  font-size: 0.85rem;
}
.combatant-power {
  color: var(--color-warning);
  font-size: 0.65rem;
  font-variant-numeric: tabular-nums;
}
.combatant-name,
.stage-empty,
.enemy-count,
.hazard-state span {
  color: var(--color-theme-primary);
  opacity: 0.7;
}
.stage-axis {
  position: relative;
  display: grid;
  place-items: center;
  color: var(--color-danger);
  font-size: 1.5rem;
}
.stage-side--threat {
  text-align: right;
}
.combatants--enemies {
  justify-content: flex-end;
  align-items: center;
}
.enemy-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--color-danger);
}
.hazard-state {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  color: var(--color-warning);
  font-size: 0.7rem;
  text-align: left;
}
.hazard-state > div {
  width: min(12rem, 100%);
}
.hazard-icon {
  width: 2rem;
  height: 2rem;
  color: var(--color-warning);
}
.hazard-flame {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
}
.flame-outer,
.flame-inner {
  transform-box: fill-box;
  transform-origin: 50% 100%;
}
.flame-outer {
  fill: var(--color-warning);
  animation: flame-flicker 1.4s ease-in-out infinite;
}
.flame-inner {
  fill: var(--color-danger);
  animation: flame-flicker 1.05s ease-in-out infinite reverse;
}
@keyframes flame-flicker {
  0%,
  100% {
    opacity: 0.92;
    transform: scale(1, 1);
  }
  35% {
    opacity: 1;
    transform: scale(0.97, 1.06);
  }
  70% {
    opacity: 0.86;
    transform: scale(1.03, 0.96);
  }
}
@media (prefers-reduced-motion: reduce) {
  .flame-outer,
  .flame-inner {
    animation: none;
  }
}
@media (max-width: 640px) {
  .incident-scene {
    grid-template-columns: 1fr;
  }
  .stage-axis {
    transform: rotate(90deg);
  }
  .stage-side--threat,
  .hazard-state {
    text-align: left;
    justify-content: flex-start;
  }
  .combatants--enemies {
    justify-content: flex-start;
  }
}
@keyframes float-effect {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-1.5rem);
  }
}
</style>
