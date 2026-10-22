<script setup lang="ts">
import { computed } from 'vue'
import { UserRound, PawPrint, Plus } from '@lucide/vue'
import type { ArenaFighter, ArenaRoomState } from '../api/arena'
import { creatureKeyOf } from '../models/arena'
import { getCreatureImagePath } from '@/core/utils/creatureAssets'
import { getStaticImageUrl } from '@/core/utils/image'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { getDwellerPortraitScale } from '@/modules/dwellers/models/dweller'
import ArenaRing from './ArenaRing.vue'
import CombatantMeters from './CombatantMeters.vue'
import { useFallbackImage } from '../composables/useFallbackImage'

interface Props {
  state: ArenaRoomState | null
  sceneImageUrl?: string | null
  pendingSkills?: Set<string>
  attackingTeam?: 'A' | 'B' | null
  attackingFighterId?: string | null
  damageNumbers?: Array<{ id: number; fighterId: string; amount: number }>
  skillBurst?: { id: string; message: string } | null
}

const props = withDefaults(defineProps<Props>(), {
  sceneImageUrl: null,
  pendingSkills: () => new Set<string>(),
  attackingTeam: null,
  attackingFighterId: null,
  damageNumbers: () => [],
  skillBurst: null,
})

const emit = defineEmits<{ skill: [fighterId: string] }>()

const { url: scene, onError: imageFailed } = useFallbackImage(() => [props.sceneImageUrl])

const mode = computed(() => props.state?.mode ?? 'duel')
const isFighting = computed(() => !!props.state?.fight_started && !props.state.match_done)
const countdown = computed(() => props.state?.countdown_remaining ?? 0)
const slotCount = computed(() => (mode.value === 'duel' ? 1 : 2))

const slotsFor = (side: 'A' | 'B'): Array<ArenaFighter | null> => {
  const team = side === 'A' ? (props.state?.team_a ?? []) : (props.state?.team_b ?? [])
  return Array.from({ length: slotCount.value }, (_, index) => team[index] ?? null)
}

const teamALabel = 'TEAM A'
const teamBLabel = computed(() => (mode.value === 'hunt' ? 'CREATURES' : 'TEAM B'))

const emptySilhouetteUrl = getStaticImageUrl(
  '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp'
)

const dwellerScale = (fighter: ArenaFighter) =>
  getDwellerPortraitScale({
    age_group: fighter.age_group,
    visual_attributes: fighter.race ? { race: fighter.race } : null,
  })

const actionFor = (fighter: ArenaFighter) => {
  const skill = fighter.active_skill
  if (!skill) return null
  return {
    name: skill.name,
    charge: skill.charge,
    queued: skill.queued,
    pending: false,
    enabled: false,
  }
}

const imageFor = (fighter: ArenaFighter) =>
  fighter.is_creature || fighter.is_robot
    ? getStaticImageUrl(getCreatureImagePath(creatureKeyOf(fighter.id)))
    : null
</script>

<template>
  <div class="arena-preview-shell relative w-full">
    <ArenaRing
      v-if="isFighting && state"
      :state="state"
      :scene-image-url="sceneImageUrl"
      :skill-enabled="countdown === 0"
      :pending-skills="pendingSkills"
      :attacking-team="attackingTeam"
      :attacking-fighter-id="attackingFighterId"
      :damage-numbers="damageNumbers"
      @skill="emit('skill', $event)"
    />

    <section
      v-else
      class="arena-preview relative isolate w-full min-w-0 overflow-hidden rounded-lg border border-theme-primary/30 bg-surface-sunken"
      aria-label="Arena preview"
    >
      <img
        v-if="scene"
        :src="scene ?? undefined"
        alt=""
        class="absolute inset-0 h-full w-full object-cover"
        @error="imageFailed"
      />
      <div class="absolute inset-0 bg-gradient-to-t from-black/45 via-transparent to-black/20" />

      <span class="absolute left-4 top-3 text-xs font-semibold tracking-wider text-theme-primary">
        {{ teamALabel }}
      </span>
      <span class="absolute right-4 top-3 text-xs font-semibold tracking-wider text-theme-primary">
        {{ teamBLabel }}
      </span>

      <div
        class="absolute inset-x-3 bottom-5 grid grid-cols-2 items-end gap-8 sm:inset-x-8 sm:bottom-8 sm:gap-16"
      >
        <div
          v-for="side in ['A', 'B'] as const"
          :key="side"
          class="flex min-w-0 items-end justify-around gap-2"
          :class="{ 'flex-row-reverse': side === 'B' }"
        >
          <div
            v-for="(fighter, index) in slotsFor(side)"
            :key="fighter?.id ?? `${side}-${index}`"
            class="flex min-w-0 max-w-28 flex-1 flex-col items-center gap-1"
          >
            <template v-if="fighter">
              <CombatantMeters
                :name="fighter.name"
                :health="fighter.health"
                :max-health="fighter.max_health"
                :tone="side === 'A' ? 'success' : 'danger'"
                :action="actionFor(fighter)"
              />
              <div class="relative flex h-32 w-full shrink-0 items-end justify-center sm:h-44">
                <img
                  v-if="imageFor(fighter)"
                  :src="imageFor(fighter) ?? undefined"
                  :alt="fighter.name"
                  class="size-full object-contain drop-shadow-lg"
                  :class="{ '-scale-x-100': side === 'B' && fighter.is_robot }"
                />
                <DwellerPortrait
                  v-else-if="!fighter.is_creature && !fighter.is_robot"
                  :image-url="fighter.image_url"
                  :thumbnail-url="fighter.thumbnail_url"
                  :alt="fighter.name"
                  :class="{ '-scale-x-100': side === 'B' }"
                  object-position="center top"
                  :scale="dwellerScale(fighter)"
                  image-class="size-full object-contain drop-shadow-lg"
                  fallback-class="hidden"
                />
                <PawPrint v-else class="size-14 text-danger" />
                <UserRound
                  v-if="
                    !fighter.is_creature &&
                    !fighter.is_robot &&
                    !fighter.image_url &&
                    !fighter.thumbnail_url
                  "
                  class="absolute bottom-0 h-32 w-16 text-theme-primary sm:h-44 sm:w-20"
                  :class="{ '-scale-x-100': side === 'B' }"
                />
              </div>
            </template>

            <div v-else class="arena-empty-slot" aria-hidden="true">
              <span
                class="arena-dweller-silhouette"
                :style="{
                  '--dweller-silhouette': emptySilhouetteUrl
                    ? `url('${emptySilhouetteUrl}')`
                    : 'none',
                }"
              />
              <Plus class="arena-empty-plus" />
            </div>
          </div>
        </div>
      </div>
    </section>

    <div
      v-if="skillBurst"
      :key="skillBurst.id"
      role="status"
      class="absolute inset-x-4 top-1/2 z-30 -translate-y-1/2 rounded border border-warning/40 bg-black/85 px-3 py-2 text-center text-xs font-semibold text-warning"
    >
      {{ skillBurst.message }}
    </div>
  </div>
</template>

<style scoped>
.arena-preview {
  min-height: 250px;
  aspect-ratio: 2 / 1;
}

.arena-empty-slot {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 8rem;
  align-items: center;
  justify-content: center;
}

.arena-dweller-silhouette {
  display: block;
  width: 100%;
  height: 8rem;
  background-color: var(--color-surface-sunken);
  -webkit-mask-image: var(--dweller-silhouette);
  mask-image: var(--dweller-silhouette);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center bottom;
  mask-position: center bottom;
  -webkit-mask-size: contain;
  mask-size: contain;
  -webkit-mask-mode: alpha;
  mask-mode: alpha;
  opacity: 0.65;
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--color-theme-primary) 30%, transparent));
}

@media (min-width: 640px) {
  .arena-empty-slot {
    min-height: 11rem;
  }

  .arena-dweller-silhouette {
    height: 11rem;
  }
}

.arena-empty-plus {
  position: absolute;
  right: 0.15rem;
  bottom: 0.15rem;
  width: 1rem;
  height: 1rem;
  color: var(--color-theme-primary);
  opacity: 0.75;
}
</style>
