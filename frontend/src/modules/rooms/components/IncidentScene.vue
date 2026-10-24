<script setup lang="ts">
import {
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from '@/core/components/ui/tooltip'

import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Heart, ShieldAlert, UserRound } from '@lucide/vue'
import { Progress } from '@/core/components/ui/progress'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getCombatPower, getEffectiveMaxHealth } from '@/modules/dwellers/models/dweller'
import {
  IncidentType,
  getIncidentParticipants,
  getIncidentIcon,
  type Incident,
  type IncidentTeamMember,
} from '@/modules/combat/models/incident'
import { getCreatureImagePath, getCreatureModelSizeClass } from '@/core/utils/creatureAssets'
import { getStaticImageUrl } from '@/core/utils/image'
import { humanizePreserveCase } from '@/core/utils/format'
import { useCombatPulse } from '../composables/useCombatPulse'
import { useFallbackImage } from '../composables/useFallbackImage'

const props = defineProps<{
  incident: Incident
  dwellers: DwellerShort[]
  roomImageUrl?: string | null
  fallbackImageUrl?: string | null
  team?: IncidentTeamMember[]
}>()

const { url: sceneImageUrl, onError: imageFailed } = useFallbackImage(() => [
  props.roomImageUrl,
  props.fallbackImageUrl,
])

const responders = computed(() =>
  getIncidentParticipants(props.incident.room_id, props.dwellers, props.team)
)
const healthCeiling = (dweller: DwellerShort) =>
  Math.max(
    1,
    dweller.effective_max_health ?? getEffectiveMaxHealth(dweller.radiation, dweller.max_health)
  )
const remainingEnemies = computed(() =>
  Math.max(0, props.incident.progress.target - props.incident.progress.current)
)
const progressPercent = computed(() =>
  props.incident.progress.target > 0
    ? Math.min(
        100,
        Math.max(0, (props.incident.progress.current / props.incident.progress.target) * 100)
      )
    : 0
)
const creatureKeys: Partial<Record<IncidentType, string>> = {
  [IncidentType.RADROACH_INFESTATION]: 'radroach',
  [IncidentType.MOLE_RAT_ATTACK]: 'mole-rat',
  [IncidentType.DEATHCLAW_ATTACK]: 'deathclaw',
  [IncidentType.FERAL_GHOUL_ATTACK]: 'feral-ghoul',
  [IncidentType.RADSCORPION_ATTACK]: 'radscorpion',
}
const creatureKey = computed(() => creatureKeys[props.incident.type])
const { url: creatureImage, onError: creatureFailed } = useFallbackImage(() => [
  getStaticImageUrl(getCreatureImagePath(creatureKey.value ?? '')),
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
  'combat-impact': combatPulse.value && dwellerDamage.value > 0,
  'combat-lunge-right': combatPulse.value && dwellerDamage.value <= 0 && threatDamage.value > 0,
}))
const threatMotion = computed(() => ({
  'combat-impact': combatPulse.value && (threatDamage.value > 0 || containmentGain.value > 0),
  'combat-lunge-left':
    combatPulse.value &&
    threatDamage.value <= 0 &&
    containmentGain.value <= 0 &&
    dwellerDamage.value > 0,
}))
</script>

<template>
  <TooltipProvider :delay-duration="200" :ignore-non-keyboard-focus="true">
    <section
      class="incident-scene relative isolate aspect-[5/2] min-h-80 w-full min-w-0 overflow-hidden rounded-lg border border-theme-primary/30 bg-surface-sunken"
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
        class="absolute inset-x-3 top-12 bottom-16 grid grid-cols-2 items-end gap-5 sm:inset-x-6 sm:gap-10"
      >
        <div class="relative min-w-0" :class="responderMotion">
          <span
            v-if="dwellerDamage"
            :key="roundKey"
            class="floating-effect absolute -top-3 left-1/2 z-30 font-bold text-danger"
            aria-hidden="true"
            >-{{ Math.round(dwellerDamage) }}</span
          >
          <!-- Keep responders spread across their half of the scene instead of clustering left. -->
          <div class="flex w-full min-w-0 items-end justify-evenly gap-2 overflow-x-auto pt-6 pb-1">
            <div
              v-for="responder in responders"
              :key="responder.id"
              class="incident-responder relative flex w-[4.85rem] min-w-[4.85rem] max-w-[4.85rem] shrink-0 flex-col items-center gap-1"
              :class="{
                'opacity-40 grayscale': responder.dweller && responder.dweller.health <= 0,
              }"
            >
              <Tooltip
                ><TooltipTrigger as-child
                  ><span
                    class="w-full truncate text-center text-xs font-semibold text-theme-primary [text-shadow:0_1px_3px_black]"
                    tabindex="0"
                    >{{ responder.name }}</span
                  ></TooltipTrigger
                ><TooltipContent
                  class="border border-theme-primary/40 bg-popover text-theme-primary"
                  >{{ responder.name }}</TooltipContent
                ></Tooltip
              >
              <Tooltip v-if="responder.dweller"
                ><TooltipTrigger as-child
                  ><div class="w-full rounded bg-black/85 p-1" tabindex="0">
                    <div class="flex items-center gap-1">
                      <Heart class="size-3 shrink-0 fill-danger text-danger" aria-hidden="true" />
                      <Progress
                        size="xs"
                        :model-value="
                          (responder.dweller.health / healthCeiling(responder.dweller)) * 100
                        "
                        :label="`${responder.name} health`"
                        :value-text="`${responder.dweller.health}/${healthCeiling(responder.dweller)}`"
                      />
                    </div>
                    <span class="sr-only"
                      >POW {{ getCombatPower(responder.dweller) }} · Lv
                      {{ responder.dweller.level }}</span
                    >
                  </div></TooltipTrigger
                ><TooltipContent
                  class="border border-theme-primary/40 bg-popover text-theme-primary"
                  >{{
                    `${responder.dweller.health}/${healthCeiling(responder.dweller)} HP · Lv ${responder.dweller.level} · POW ${getCombatPower(responder.dweller)}`
                  }}</TooltipContent
                ></Tooltip
              >
              <div class="flex h-[7.25rem] w-full items-end justify-center">
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
              </div>
              <span
                v-if="responder.source === 'resident'"
                class="max-w-full truncate rounded bg-black/80 px-1 text-[9px] font-semibold text-theme-primary"
                >RESIDENT</span
              >
              <span
                v-else-if="responder.dispatched"
                class="max-w-full truncate rounded bg-black/80 px-1 text-[9px] font-semibold text-info"
                >DISPATCHED</span
              >
              <span
                v-else
                class="max-w-full truncate rounded bg-black/80 px-1 text-[9px] font-semibold text-info"
                >HELPER</span
              >
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
            threatMotion,
            { 'opacity-40 grayscale': incident.objective === 'defeat' && remainingEnemies === 0 },
          ]"
        >
          <span
            v-if="threatDamage && incident.objective === 'defeat'"
            :key="roundKey"
            class="floating-effect absolute -top-3 z-30 font-bold text-danger"
            aria-hidden="true"
            >-{{ Math.round(threatDamage) }}</span
          >
          <span
            v-if="containmentGain && incident.objective === 'contain'"
            :key="roundKey"
            class="floating-effect absolute -top-3 z-30 font-bold text-success"
            aria-hidden="true"
            >+{{ containmentGain }}%</span
          >
          <svg
            v-if="incident.type === 'fire'"
            class="hazard-flame h-32 w-24 drop-shadow-lg sm:h-44 sm:w-32"
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
          <div
            v-else-if="creatureImage"
            class="flex max-w-full origin-bottom scale-110 items-end justify-center sm:scale-125"
            :class="getCreatureModelSizeClass(creatureKey ?? '')"
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
            class="h-28 w-20 text-danger drop-shadow-lg sm:h-36 sm:w-24"
            role="img"
            aria-label="Raider"
          />
          <Icon
            v-else
            :icon="getIncidentIcon(incident.type)"
            class="hazard-icon size-24 text-warning"
            :ariaHidden="true"
          />
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
            >{{ incident.progress.label }} · {{ incident.progress.current }} /
            {{ incident.progress.target }}</span
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
  </TooltipProvider>
</template>

<style scoped>
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
