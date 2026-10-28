<script setup lang="ts">
import { computed } from 'vue'
import { UserRound, PawPrint } from '@lucide/vue'
import CombatSkillIcon from '@/modules/combat/components/CombatSkillIcon.vue'
import type { ArenaFighter, ArenaRoomState } from '../api/arena'
import { creatureKeyOf } from '../models/arena'
import {
  creatureSeed,
  getActorModelSizeClass,
  getCreatureImagePath,
  getCreatureHoverClass,
  getCreatureModelSizeClass,
} from '@/core/utils/creatureAssets'
import { getStaticImageUrl } from '@/core/utils/image'
import { Button } from '@/core/components/ui/button'
import {
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from '@/core/components/ui/tooltip'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { getDwellerPortraitScale } from '@/modules/dwellers/models/dweller'
import CombatDamageNumbers from '@/modules/combat/components/CombatDamageNumbers.vue'
import CombatantMeters from './CombatantMeters.vue'
import CombatantMotion from '@/modules/combat/components/CombatantMotion.vue'
import CombatPet from '@/modules/combat/components/CombatPet.vue'
import type { PlayingCombatAction } from '@/modules/combat/models/playback'
import { useFallbackImage } from '../composables/useFallbackImage'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    state: Pick<
      ArenaRoomState,
      'team_a' | 'team_b' | 'match_done' | 'fight_started' | 'next_attack_team'
    > &
      Partial<Pick<ArenaRoomState, 'mode' | 'countdown_remaining'>>
    sceneImageUrl?: string | null
    sceneSrcset?: string
    wideSceneImageUrl?: string
    wideSceneSrcset?: string
    encounter?: boolean
    contained?: boolean
    heading?: string
    teamALabel?: string
    teamBLabel?: string
    statusLabel?: string
    skillEnabled: boolean
    pendingSkills?: Set<string>
    attackingTeam?: 'A' | 'B' | null
    attackingFighterId?: string | null
    damageNumbers: Array<{ id: number; fighterId: string; amount: number }>
    activeAction?: PlayingCombatAction | null
    combatPhase?: 'prepare' | 'impact' | null
  }>(),
  {
    pendingSkills: () => new Set<string>(),
    attackingTeam: null,
  }
)
const emit = defineEmits<{ skill: [fighterId: string] }>()
const { url: scene, onError: imageFailed } = useFallbackImage(() => [props.sceneImageUrl])
const teams = computed<Array<{ side: 'A' | 'B'; fighters: ArenaFighter[] }>>(() => [
  { side: 'A', fighters: props.state.team_a },
  { side: 'B', fighters: props.state.team_b },
])
// Match the server's standing-fighter slot order for ordinary targets.
const readySkills = computed(() => {
  if (!props.skillEnabled) return []
  return teams.value.flatMap((team, teamIndex) => {
    const targets = teams.value[1 - teamIndex].fighters.filter((fighter) => fighter.health > 0)
    if (!targets.length) return []
    return team.fighters
      .filter((fighter) => fighter.health > 0)
      .flatMap((fighter, index) => {
        const skill = fighter.active_skill
        return skill && skill.charge >= 100 && !skill.queued && !props.pendingSkills.has(fighter.id)
          ? [{ fighter, skill, targetId: targets[index % targets.length].id }]
          : []
      })
  })
})
const imageFor = (fighter: ArenaFighter) =>
  fighter.image_url
    ? getStaticImageUrl(fighter.image_url)
    : getStaticImageUrl(getCreatureImagePath(creatureKeyOf(fighter.id), creatureSeed(fighter.id)))
const actorSizeClass = (fighter: ArenaFighter) =>
  fighter.is_creature || fighter.is_robot
    ? getCreatureModelSizeClass(creatureKeyOf(fighter.id))
    : getActorModelSizeClass(
        getDwellerPortraitScale({
          age_group: fighter.age_group,
          visual_attributes: fighter.race ? { race: fighter.race } : null,
        })
      )

const isAttacking = (fighter: ArenaFighter, side: 'A' | 'B') =>
  fighter.health > 0 &&
  (props.attackingFighterId
    ? props.attackingFighterId === fighter.id
    : props.attackingTeam === side)

const actionFor = (fighter: ArenaFighter) => {
  const skill = fighter.active_skill
  if (!skill) return null
  return {
    name: skill.name,
    icon: skill.icon,
    charge: skill.charge,
    queued: skill.queued,
    pending: props.pendingSkills.has(fighter.id),
    enabled: props.skillEnabled && fighter.health > 0,
  }
}
</script>

<template>
  <TooltipProvider :delay-duration="200">
    <section
      v-bind="$attrs"
      class="arena-ring isolate min-w-0 overflow-hidden rounded-lg border border-theme-primary/30 bg-surface-sunken [container-type:size]"
      :class="{
        'arena-ring--encounter': encounter,
        'arena-ring--wide': encounter && wideSceneImageUrl,
        'relative w-full': !contained,
        absolute: contained,
      }"
      :aria-label="heading ?? 'Arena ring'"
    >
      <picture v-if="scene">
        <source
          v-if="wideSceneImageUrl"
          media="(min-width: 1024px)"
          :srcset="wideSceneSrcset ?? wideSceneImageUrl"
          sizes="calc(100vw - 24rem)"
        />
        <img
          :src="scene"
          :srcset="sceneSrcset"
          :sizes="encounter ? '(max-width: 1024px) calc(100vw - 64px), 600px' : undefined"
          :alt="heading ?? 'Arena'"
          class="absolute inset-0 size-full object-cover"
          @error="imageFailed"
        />
      </picture>
      <div
        class="absolute inset-x-0 top-0 flex justify-between bg-black/70 px-3 py-2 text-[10px] font-semibold text-theme-primary"
      >
        <span>{{ teamALabel ?? 'TEAM A' }}</span>
        <span aria-live="polite">{{
          statusLabel ??
          (state.match_done
            ? 'MATCH COMPLETE'
            : (state.countdown_remaining ?? 0) > 0
              ? 'GET READY'
              : state.fight_started
                ? `NEXT · TEAM ${state.next_attack_team}`
                : 'READY TO FIGHT')
        }}</span>
        <span>{{
          teamBLabel ??
          (state.mode === 'training' ? 'BOTS' : state.mode === 'hunt' ? 'CREATURES' : 'TEAM B')
        }}</span>
      </div>
      <div
        v-if="state.fight_started && !state.match_done && (state.countdown_remaining ?? 0) > 0"
        class="pointer-events-none absolute inset-0 z-30 flex flex-col items-center justify-center gap-2 bg-black/30"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span class="text-xs font-semibold tracking-widest text-white">STARTING IN</span>
        <Transition name="countdown-pop" mode="out-in" appear>
          <span
            :key="state.countdown_remaining"
            class="countdown-number text-7xl font-bold tabular-nums text-theme-primary [text-shadow:0_0_24px_black] sm:text-8xl"
            >{{ state.countdown_remaining }}</span
          >
        </Transition>
      </div>
      <!-- Reserve meters and stagger headroom for the largest (1.5x) actor. -->
      <div
        class="absolute grid grid-cols-2 [--scene-actor-height:min(36cqh,max(0px,calc((100cqh-7rem-var(--scene-stagger))/1.5)))]"
        :class="[
          contained
            ? 'inset-x-[6%] bottom-[6%] gap-[12%]'
            : 'inset-x-3 bottom-5 gap-8 sm:inset-x-8 sm:bottom-8 sm:gap-16',
          teams.some((team) => team.fighters.length > 1)
            ? '[--scene-stagger:min(2rem,8cqh)] sm:[--scene-stagger:min(3rem,8cqh)]'
            : '[--scene-stagger:0px]',
        ]"
      >
        <div
          v-for="team in teams"
          :key="team.side"
          class="flex min-w-0 items-end justify-around gap-2"
          :class="{ 'flex-row-reverse': team.side === 'B' }"
        >
          <div
            v-for="(fighter, index) in team.fighters"
            :key="fighter.id"
            class="ring-fighter relative flex min-w-0 max-w-[max(4rem,var(--scene-actor-height))] flex-1 flex-col items-center gap-1"
            :aria-current="isAttacking(fighter, team.side) ? 'true' : undefined"
            :class="[
              {
                'bottom-[var(--scene-stagger)] z-0 scale-90': index % 2 === 1,
                'z-10': index % 2 === 0,
              },
              // Center solo fighters; offset only multi-fighter lanes.
              team.fighters.length > 1 && {
                'left-4 sm:left-6': index % 2 === 0 && team.side === 'A',
                'right-4 sm:right-6': index % 2 === 0 && team.side === 'B',
                'right-2 sm:right-3': index % 2 === 1 && team.side === 'A',
                'left-2 sm:left-3': index % 2 === 1 && team.side === 'B',
              },
            ]"
          >
            <CombatDamageNumbers
              :numbers="damageNumbers.filter((d) => d.fighterId === fighter.id)"
            />
            <CombatantMeters
              class="fighter-meters max-w-32"
              :class="[
                getCreatureHoverClass(creatureKeyOf(fighter.id)),
                { 'opacity-40 grayscale': fighter.health <= 0 },
              ]"
              :name="fighter.name"
              :health="fighter.health"
              :max-health="fighter.max_health"
              :tone="team.side === 'A' ? 'success' : 'danger'"
              :action="actionFor(fighter)"
              @skill="emit('skill', fighter.id)"
            />
            <div
              class="fighter-portrait relative flex shrink-0 items-end justify-center"
              :class="actorSizeClass(fighter)"
            >
              <div
                class="absolute inset-x-0 top-1/3 z-20 flex flex-wrap justify-center gap-1"
                :class="getCreatureHoverClass(creatureKeyOf(fighter.id))"
              >
                <Tooltip
                  v-for="ready in readySkills.filter((entry) => entry.targetId === fighter.id)"
                  :key="ready.fighter.id"
                >
                  <TooltipTrigger as-child>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      class="flex size-10 shrink-0 items-center justify-center rounded-full border-2 border-theme-primary bg-black/85 text-theme-primary shadow-lg motion-safe:animate-pulse hover:bg-theme-primary hover:text-black focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary sm:size-11"
                      :aria-label="`Use ${ready.skill.name} from ${ready.fighter.name} on ${fighter.name}`"
                      @click="emit('skill', ready.fighter.id)"
                    >
                      <CombatSkillIcon :icon="ready.skill.icon" class="size-6" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent
                    class="border border-theme-primary/40 bg-popover text-theme-primary"
                  >
                    <span class="flex flex-col gap-1"
                      ><strong class="flex items-center gap-1.5"
                        ><CombatSkillIcon :icon="ready.skill.icon" class="size-4" />{{
                          ready.fighter.name
                        }}
                        · {{ ready.skill.name }}</strong
                      ><span>{{ ready.skill.description }}</span
                      ><span>Activate skill against {{ fighter.name }}</span></span
                    >
                  </TooltipContent>
                </Tooltip>
              </div>
              <CombatantMotion
                class="actor-ground-shadow"
                :class="{ 'opacity-40 grayscale': fighter.health <= 0 }"
                :fighter-id="fighter.id"
                :facing="team.side === 'B' ? 'left' : 'right'"
                :action="activeAction"
                :phase="combatPhase"
              >
                <template v-if="fighter.is_creature || fighter.is_robot">
                  <img
                    v-if="imageFor(fighter)"
                    :src="imageFor(fighter) ?? undefined"
                    :alt="fighter.name"
                    class="size-full object-contain drop-shadow-lg"
                    :class="[
                      getCreatureHoverClass(creatureKeyOf(fighter.id)),
                      { '-scale-x-100': team.side === 'B' && fighter.is_robot },
                    ]"
                  />
                  <PawPrint v-else class="size-full text-danger" />
                </template>
                <DwellerPortrait
                  v-else
                  :image-url="fighter.image_url"
                  :thumbnail-url="fighter.thumbnail_url"
                  :alt="fighter.name"
                  :class="{ '-scale-x-100': team.side === 'B' }"
                  object-position="center top"
                  :zoom="false"
                  image-class="size-full object-contain drop-shadow-lg"
                  fallback-class="hidden"
                />
                <UserRound
                  v-if="
                    !fighter.is_creature &&
                    !fighter.is_robot &&
                    !fighter.image_url &&
                    !fighter.thumbnail_url
                  "
                  class="absolute bottom-0 size-full text-theme-primary"
                  :class="{ '-scale-x-100': team.side === 'B' }"
                />
              </CombatantMotion>
              <CombatPet
                v-if="fighter.pet && !fighter.is_creature && !fighter.is_robot"
                :pet="fighter.pet"
                :owner-name="fighter.name"
                :owner-id="fighter.id"
                :action="activeAction"
                :phase="combatPhase"
                :facing="team.side === 'B' ? 'left' : 'right'"
              />
            </div>
            <span
              v-if="fighter.health <= 0"
              class="absolute bottom-0 rounded bg-black/80 px-2 text-xs font-bold text-danger"
              >KO</span
            >
            <span
              v-else-if="fighter.active_skill?.queued"
              class="absolute -bottom-4 text-[9px] text-warning"
              >QUEUED</span
            >
          </div>
        </div>
      </div>
    </section>
  </TooltipProvider>
</template>

<style scoped>
.arena-ring {
  min-height: 250px;
  aspect-ratio: 2 / 1;
}
.arena-ring--encounter {
  min-height: 0;
  aspect-ratio: 50 / 37;
}
@media (min-width: 1024px) {
  .arena-ring--wide {
    aspect-ratio: 16 / 9;
  }
}
.countdown-pop-enter-active,
.countdown-pop-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}
.countdown-pop-enter-from {
  opacity: 0;
  transform: scale(1.6);
}
.countdown-pop-leave-to {
  opacity: 0;
  transform: scale(0.6);
}
@media (prefers-reduced-motion: reduce) {
  .countdown-pop-enter-active,
  .countdown-pop-leave-active {
    transition: none;
  }
}
</style>
