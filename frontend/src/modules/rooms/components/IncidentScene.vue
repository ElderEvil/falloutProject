<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { ShieldAlert, UserRound } from '@lucide/vue'
import { Progress } from '@/core/components/ui/progress'
import DwellerNameBadge from '@/modules/dwellers/components/DwellerNameBadge.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getEffectiveMaxHealth } from '@/modules/dwellers/models/dweller'
import {
  IncidentType,
  getIncidentParticipants,
  getIncidentIcon,
  type Incident,
  type IncidentTeamMember,
  type IncidentParticipant,
} from '@/modules/combat/models/incident'
import {
  creatureSeed,
  getCreatureImagePath,
  getCreatureModelSizeClass,
} from '@/core/utils/creatureAssets'
import { getStaticImageUrl } from '@/core/utils/image'
import { humanizePreserveCase } from '@/core/utils/format'
import { useCombatPulse } from '../composables/useCombatPulse'
import { useFallbackImage } from '../composables/useFallbackImage'
import { useCombatPlayback } from '@/modules/combat/composables/useCombatPlayback'
import CombatantMotion from '@/modules/combat/components/CombatantMotion.vue'
import CombatPet from '@/modules/combat/components/CombatPet.vue'
import CombatDamageNumbers from '@/modules/combat/components/CombatDamageNumbers.vue'
import { useSound } from '@/core/composables/useSound'

const props = defineProps<{
  incident: Incident
  dwellers: DwellerShort[]
  roomImageUrl?: string | null
  fallbackImageUrl?: string | null
  team?: IncidentTeamMember[]
}>()
const emit = defineEmits<{ playbackComplete: [incidentId: string] }>()
const { playSound } = useSound()
const playback = useCombatPlayback(
  () => {
    return {
      key: `${props.incident.vault_id}:${props.incident.id}:${props.incident.room_id}`,
      health: Object.fromEntries(props.dwellers.map((dweller) => [dweller.id, dweller.health])),
      events: props.incident.events,
    }
  },
  () => playSound('incidentHit', 'sfx')
)
const structured = computed(() => props.incident.events.some((event) => event.action))
const activeAction = playback.active
const combatPhase = playback.phase
const damageNumbers = playback.damageNumbers
const isAttacking = (id: string) => activeAction.value?.action.actor_id === id
const displayedHealth = (dweller: DwellerShort) =>
  playback.health.value[dweller.id] ?? dweller.health
const displayedProgress = shallowRef(props.incident.progress)
watch(
  () => [props.incident.progress, playback.isPlaying.value] as const,
  ([progress, playing]) => {
    if (!playing) displayedProgress.value = progress
  }
)
const cuePending = ref(!['resolved', 'failed'].includes(props.incident.status))
watch(
  () => [props.incident.status, playback.isPlaying.value] as const,
  ([status, playing]) => {
    if (playing || !['resolved', 'failed'].includes(status)) return
    if (cuePending.value) {
      cuePending.value = false
      playSound(status === 'resolved' ? 'incidentVictory' : 'incidentDefeat', 'sfx')
    }
    emit('playbackComplete', props.incident.id)
  },
  { immediate: true }
)

const { url: sceneImageUrl, onError: imageFailed } = useFallbackImage(() => [
  props.roomImageUrl,
  props.fallbackImageUrl,
])

const currentResponders = computed(() =>
  getIncidentParticipants(props.incident.room_id, props.dwellers, props.team)
)
const previousResponders = shallowRef<IncidentParticipant[]>([])
watch(
  () => props.incident.id,
  () => {
    previousResponders.value = []
  }
)
const responders = computed(() => {
  const current = currentResponders.value
  if (!playback.isPlaying.value) return current
  const currentIds = new Set(current.map((responder) => responder.id))
  const finishing = ['resolved', 'failed'].includes(props.incident.status)
  return [
    ...current,
    ...previousResponders.value.filter(
      (responder) =>
        !currentIds.has(responder.id) &&
        (finishing ||
          isAttacking(responder.id) ||
          activeAction.value?.action.targets.some((target) => target.target_id === responder.id))
    ),
  ]
})
watch(
  currentResponders,
  (current) => {
    const currentIds = new Set(current.map((responder) => responder.id))
    const retained = previousResponders.value.filter((responder) => !currentIds.has(responder.id))
    previousResponders.value = [...current, ...retained].map((responder) => ({
      ...responder,
      dweller: responder.dweller ? { ...responder.dweller } : undefined,
    }))
  },
  { immediate: true }
)
const healthCeiling = (dweller: DwellerShort) =>
  Math.max(
    1,
    dweller.effective_max_health ?? getEffectiveMaxHealth(dweller.radiation, dweller.max_health)
  )
const remainingEnemies = computed(() =>
  Math.max(0, displayedProgress.value.target - displayedProgress.value.current)
)
const progressPercent = computed(() =>
  displayedProgress.value.target > 0
    ? Math.min(
        100,
        Math.max(0, (displayedProgress.value.current / displayedProgress.value.target) * 100)
      )
    : 0
)
const creatureKeys: Partial<Record<IncidentType, string>> = {
  [IncidentType.RAIDER_ATTACK]: 'raider',
  [IncidentType.RADROACH_INFESTATION]: 'radroach',
  [IncidentType.MOLE_RAT_ATTACK]: 'mole-rat',
  [IncidentType.DEATHCLAW_ATTACK]: 'deathclaw',
  [IncidentType.FERAL_GHOUL_ATTACK]: 'feral-ghoul',
  [IncidentType.RADSCORPION_ATTACK]: 'radscorpion',
}
const creatureKey = computed(() => creatureKeys[props.incident.type])
const { url: creatureImage, onError: creatureFailed } = useFallbackImage(() => [
  getStaticImageUrl(getCreatureImagePath(creatureKey.value ?? '', creatureSeed(props.incident.id))),
])
const creatureName = computed(() =>
  humanizePreserveCase((creatureKey.value ?? 'Raider').replaceAll('-', '_'))
)
// A round is a `turn` line followed by one `hit` line per attack, so the scene
// sums the whole round instead of reading a single aggregate event.
const latestTurnIndex = computed(() => {
  const events = props.incident.events
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index].kind === 'turn' || events[index].kind === 'round') return index
  }
  return -1
})
const roundEvents = computed(() => {
  if (latestTurnIndex.value >= 0) return props.incident.events.slice(latestTurnIndex.value)
  const latest = [...props.incident.events].reverse().find((event) => event.data !== null)
  return latest ? [latest] : []
})
const roundKey = computed(() => roundEvents.value[0]?.id ?? null)
const roundTotal = (key: string) =>
  roundEvents.value.reduce((total, event) => total + Number(event.data?.[key] ?? 0), 0)
const dwellerDamage = computed(() => roundTotal('damage_to_dwellers'))
const threatDamage = computed(() => roundTotal('damage_to_threat'))
const containmentGain = computed(() => Math.round(roundTotal('amount') * 100))

const combatPulse = useCombatPulse(computed(() => roundKey.value))
const responderMotion = computed(() => ({
  'combat-impact': !structured.value && combatPulse.value && dwellerDamage.value > 0,
  'combat-lunge-right':
    !structured.value && combatPulse.value && dwellerDamage.value <= 0 && threatDamage.value > 0,
}))
const threatMotion = computed(() => ({
  'combat-impact':
    !structured.value && combatPulse.value && (threatDamage.value > 0 || containmentGain.value > 0),
  'combat-lunge-left':
    !structured.value &&
    combatPulse.value &&
    threatDamage.value <= 0 &&
    containmentGain.value <= 0 &&
    dwellerDamage.value > 0,
}))
// Fire is environmental: it gets the flicker, never a fighter's lunge/shadow.
const isFire = computed(() => props.incident.type === 'fire')
const isHumanoidThreat = computed(() =>
  ['raider_attack', 'feral_ghoul_attack'].includes(props.incident.type)
)
const fireFlames = ['hazard-flame--side', 'hazard-flame--main', 'hazard-flame--tail'] as const
// Up to four responders share the scene lane; larger rosters keep the scroll.
const isCompact = computed(() => responders.value.length > 3)
const responderSizeClass = computed(() => {
  const count = responders.value.length
  if (count === 3) return 'responder-cell--3'
  return count > 3 ? 'responder-cell--4' : ''
})
</script>

<template>
  <section
    class="incident-scene relative isolate aspect-[5/2] min-h-80 w-full min-w-0 overflow-hidden rounded-lg border border-theme-primary/30 bg-surface-sunken"
    :class="{ 'is-compact': isCompact }"
    v-bind="{ 'data-incident-scene-id': incident.id }"
    aria-label="Incident live status"
  >
    <img
      v-if="sceneImageUrl"
      :src="sceneImageUrl"
      class="scene-backdrop absolute inset-0 size-full object-cover"
      alt=""
      aria-hidden="true"
      @error="imageFailed"
    />
    <div
      class="pointer-events-none absolute inset-0 bg-linear-to-t from-black/70 via-transparent to-black/30"
      aria-hidden="true"
    />
    <div
      class="absolute inset-x-0 top-0 z-20 flex items-center justify-between gap-3 bg-black/75 px-3 py-2 text-xs font-semibold text-theme-primary"
    >
      <span class="shrink-0">RESPONDERS · {{ responders.length }}</span>
      <span v-if="incident.room_name" class="hidden truncate font-normal sm:block">{{
        incident.room_name
      }}</span>
      <span>{{ incident.objective === 'defeat' ? 'THREAT' : 'ROOM HAZARD' }}</span>
    </div>

    <div
      class="scene-lanes absolute inset-x-3 top-12 bottom-16 grid items-end gap-5 sm:inset-x-6 sm:gap-10"
      :class="{ 'lane-wide': isCompact }"
    >
      <div class="relative min-w-0" :class="responderMotion">
        <span
          v-if="dwellerDamage && !structured"
          :key="roundKey"
          class="floating-effect absolute -top-3 left-1/2 z-30 font-bold text-danger"
          aria-hidden="true"
          >-{{ Math.round(dwellerDamage) }}</span
        >
        <!-- Keep responders spread across their half of the scene instead of clustering left. -->
        <div
          class="flex w-full min-w-0 items-end justify-evenly gap-1 overflow-x-auto pt-6 pb-1 sm:gap-2"
        >
          <div
            v-for="responder in responders"
            :key="responder.id"
            class="incident-responder relative flex shrink-0 flex-col items-center gap-1"
            :class="[
              responderSizeClass,
              {
                'opacity-40 grayscale':
                  responder.dweller && displayedHealth(responder.dweller) <= 0,
              },
            ]"
            :aria-current="isAttacking(responder.id) ? 'true' : undefined"
          >
            <CombatDamageNumbers
              :numbers="damageNumbers.filter((number) => number.fighterId === responder.id)"
            />
            <DwellerNameBadge
              :name="responder.dweller?.first_name ?? responder.name"
              :full-name="responder.name"
              :health="responder.dweller ? displayedHealth(responder.dweller) : undefined"
              :max-health="responder.dweller ? healthCeiling(responder.dweller) : null"
            />
            <span
              v-if="
                responder.dweller &&
                displayedHealth(responder.dweller) < healthCeiling(responder.dweller)
              "
              class="sr-only"
              >{{ responder.name }}: {{ displayedHealth(responder.dweller) }} of
              {{ healthCeiling(responder.dweller) }} HP</span
            >
            <div
              class="relative flex h-[var(--scene-actor-height)] w-full items-end justify-center"
            >
              <CombatantMotion
                :fighter-id="responder.id"
                facing="right"
                :action="activeAction"
                :phase="combatPhase"
              >
                <DwellerPortrait
                  v-if="responder.dweller?.thumbnail_url"
                  :thumbnail-url="responder.dweller.thumbnail_url"
                  :alt="responder.name"
                  image-class="incident-dweller-portrait h-full w-full object-contain drop-shadow-lg"
                  fallback-class="size-10 text-theme-primary"
                  :zoom="false"
                />
                <UserRound
                  v-else
                  class="h-full w-full max-w-16 text-theme-primary drop-shadow-lg"
                  :aria-label="responder.name"
                  role="img"
                />
              </CombatantMotion>
              <CombatPet
                v-if="responder.dweller?.pet"
                :pet="responder.dweller.pet"
                :owner-name="responder.name"
                :owner-id="responder.id"
                :action="activeAction"
                :phase="combatPhase"
                facing="right"
              />
            </div>
          </div>
          <span
            v-if="!responders.length"
            class="self-center rounded bg-black/80 p-2 text-center text-xs text-theme-primary"
            >No responders assigned</span
          >
        </div>
      </div>

      <div
        class="relative flex min-w-0 flex-col items-center justify-end gap-2 self-end"
        :class="[
          !isFire && threatMotion,
          { 'opacity-40 grayscale': incident.objective === 'defeat' && remainingEnemies === 0 },
        ]"
      >
        <span
          v-if="threatDamage && incident.objective === 'defeat' && !structured"
          :key="roundKey"
          class="floating-effect absolute -top-3 z-30 font-bold text-danger"
          aria-hidden="true"
          >-{{ Math.round(threatDamage) }}</span
        >
        <CombatDamageNumbers
          :numbers="damageNumbers.filter((number) => number.fighterId === 'threat')"
        />
        <span
          v-if="containmentGain && incident.objective === 'contain'"
          :key="roundKey"
          class="floating-effect absolute -top-3 z-30 font-bold text-success"
          aria-hidden="true"
          >+{{ containmentGain }}%</span
        >
        <div class="relative flex w-full max-w-full items-end justify-center">
          <div
            v-if="isFire"
            class="hazard-fire flex h-[var(--scene-actor-height)] w-full items-end justify-center"
            aria-hidden="true"
          >
            <svg
              v-for="(flame, index) in fireFlames"
              :key="index"
              class="hazard-flame -mx-2 w-auto drop-shadow-lg"
              :class="flame"
              viewBox="0 0 24 24"
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
          </div>
          <CombatantMotion
            v-else
            fighter-id="threat"
            facing="left"
            :action="activeAction"
            :phase="combatPhase"
          >
            <div
              v-if="creatureImage"
              class="flex max-w-full origin-bottom items-end justify-center"
              :class="[
                isHumanoidThreat ? undefined : 'sm:scale-125',
                getCreatureModelSizeClass(creatureKey ?? ''),
              ]"
            >
              <img
                :src="creatureImage"
                :alt="creatureName"
                class="size-full object-contain drop-shadow-lg"
                @error="creatureFailed"
              />
            </div>
            <UserRound
              v-else-if="incident.type === 'raider_attack'"
              class="size-full text-danger drop-shadow-lg"
              role="img"
              aria-label="Raider"
            />
            <Icon
              v-else
              :icon="getIncidentIcon(incident.type)"
              class="hazard-icon size-full p-3 text-warning"
              :ariaHidden="true"
            />
          </CombatantMotion>
        </div>
        <span
          v-if="incident.objective === 'defeat'"
          class="rounded bg-black/85 px-2 py-1 text-xs font-semibold text-theme-primary"
          >{{ remainingEnemies }} remaining</span
        >
      </div>
    </div>

    <div class="absolute inset-x-0 bottom-0 z-20 flex flex-col gap-1 bg-black/85 px-3 py-2">
      <div class="flex items-center justify-between gap-2 text-xs text-theme-primary">
        <span
          >{{ incident.progress.label }} · {{ displayedProgress.current }} /
          {{ displayedProgress.target }}</span
        >
        <span class="flex shrink-0 items-center gap-1 text-warning"
          ><ShieldAlert class="size-3.5" aria-hidden="true" />{{
            incident.risk.rooms_affected
          }}
          room{{ incident.risk.rooms_affected === 1 ? '' : 's' }} affected</span
        >
      </div>
      <Progress
        :model-value="progressPercent"
        :label="incident.progress.label"
        :tone="incident.objective === 'contain' ? 'warning' : 'default'"
        size="xs"
      />
    </div>
  </section>
</template>

<style scoped>
.incident-scene {
  --scene-actor-height: 7rem;
  max-height: 22.5rem;
}
.incident-scene.is-compact {
  --scene-actor-height: 5rem;
  --dweller-name-size: 0.55rem;
}
.scene-lanes {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.scene-lanes.lane-wide {
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
}
.responder-frame {
  height: var(--scene-actor-height);
}
.incident-responder {
  width: 4.85rem;
  min-width: 4.85rem;
  max-width: 4.85rem;
}
.incident-responder.responder-cell--3 {
  width: 3.3rem;
  min-width: 3.3rem;
  max-width: 3.3rem;
}
.incident-responder.responder-cell--4 {
  width: 2.9rem;
  min-width: 2.9rem;
  max-width: 2.9rem;
}
.hazard-flame--side {
  height: 50%;
  opacity: 0.8;
}
.hazard-flame--main {
  height: 90%;
}
.hazard-flame--tail {
  height: 65%;
  opacity: 0.9;
}
@media (min-width: 768px) {
  .incident-scene.is-compact {
    --scene-actor-height: 7rem;
    --dweller-name-size: 0.625rem;
  }
  .scene-lanes.lane-wide {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .incident-responder.responder-cell--3,
  .incident-responder.responder-cell--4 {
    width: 4.85rem;
    min-width: 4.85rem;
    max-width: 4.85rem;
  }
}
/* Incident sprites are smaller than Arena's, so the shared 4deg/4px motion
   reads as a twitch. Amplify the lean and recoil here without retuning Arena. */
.incident-scene :deep(.combat-body.combat-body) {
  --lean: 7deg;
  --travel: 16px;
  --recoil: 8px;
}
.incident-scene :deep(.combat-body.combat-body--attack),
.incident-scene :deep(.combat-body.combat-body--hit),
.incident-scene :deep(.combat-body.combat-body--recoil) {
  animation-duration: 240ms;
}
.floating-effect {
  animation: float-effect 0.9s ease-out both;
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
@media (prefers-reduced-motion: reduce) {
  .flame-outer,
  .flame-inner {
    animation: none;
  }
  .floating-effect {
    animation: none;
  }
}
</style>
