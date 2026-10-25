<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { Bot, PawPrint, Plus, X, ArrowLeftRight } from '@lucide/vue'
import { Button } from '@/core/components/ui/button'
import { Input } from '@/core/components/ui/input'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { getDwellerBodySize } from '@/modules/dwellers/models/dweller'
import { getCreatureImagePath } from '@/core/utils/creatureAssets'
import { getStaticImageUrl } from '@/core/utils/image'
import CombatSkillIcon from '@/modules/combat/components/CombatSkillIcon.vue'
import type {
  CombatSkillIcon as SkillIconKey,
  PlayingCombatAction,
} from '@/modules/combat/models/playback'
import type { ArenaCreature, ArenaRosterEntry } from '../api/arena'
import { creatureKeyOf, type ArenaSlotFighter, type ArenaTeamSide } from '../models/arena'
import type { ArenaMatchDraft } from '../composables/useArenaMatchDraft'
import { useFallbackImage } from '../composables/useFallbackImage'
import ArenaRing from './ArenaRing.vue'
import CombatantMeters from './CombatantMeters.vue'

const props = withDefaults(
  defineProps<{
    match: ArenaMatchDraft
    sceneImageUrl?: string | null
    pendingSkills?: Set<string>
    attackingTeam?: 'A' | 'B' | null
    attackingFighterId?: string | null
    damageNumbers?: Array<{ id: number; fighterId: string; amount: number }>
    skillBurst?: { id: string; message: string; icon?: SkillIconKey | null } | null
    activeAction?: PlayingCombatAction | null
    combatPhase?: 'prepare' | 'impact' | null
  }>(),
  {
    sceneImageUrl: null,
    pendingSkills: () => new Set<string>(),
    attackingTeam: null,
    attackingFighterId: null,
    damageNumbers: () => [],
    skillBurst: null,
  }
)
const emit = defineEmits<{ skill: [fighterId: string]; stop: []; assignDwellers: [] }>()
const state = computed(() => props.match.roomState)
const { url: scene, onError: imageFailed } = useFallbackImage(() => [props.sceneImageUrl])
const search = ref('')
const fighterPicker = ref<HTMLElement | null>(null)
const opponentPicker = ref<HTMLElement | null>(null)
let pickerTriggerId: string | null = null
const slotId = (side: ArenaTeamSide, index: number) =>
  `arena-slot-${props.match.roomState?.room_id}-${side}-${index}`
const closePickers = async () => {
  props.match.closePickers()
  await nextTick()
  if (pickerTriggerId) document.getElementById(pickerTriggerId)?.focus()
}
const catalogOpponents = computed(() => ['hunt', 'training'].includes(props.match.mode))
const teams = computed(() => [
  { side: 'A' as const, fighters: props.match.teamA, slots: props.match.slotKeysA },
  { side: 'B' as const, fighters: props.match.teamB, slots: props.match.slotKeysB },
])
const bodySizeFor = (fighter: ArenaSlotFighter) =>
  getDwellerBodySize({
    age_group: fighter.age_group,
    visual_attributes: fighter.race ? { race: fighter.race } : null,
  })
defineExpose({ bodySizeFor })
const isOpponent = (side: ArenaTeamSide) => side === 'B' && catalogOpponents.value
const slotLabel = (side: ArenaTeamSide, index: number) =>
  isOpponent(side)
    ? `Select ${props.match.mode === 'training' ? 'bot' : 'creature'} ${index + 1} for Team B`
    : `Select fighter ${index + 1} for Team ${side}`
const activateSlot = async (side: ArenaTeamSide, index: number) => {
  if (!props.match.canChangeFighters) return
  search.value = ''
  pickerTriggerId = slotId(side, index)
  if (isOpponent(side)) props.match.toggleCreaturePicker(index)
  else {
    const slot = teams.value.find((team) => team.side === side)?.slots[index]
    if (slot) props.match.togglePicker(slot)
  }
  await nextTick()
  if (props.match.openPicker) fighterPicker.value?.querySelector('input')?.focus()
  else if (props.match.creaturePickerOpen)
    opponentPicker.value?.querySelector<HTMLButtonElement>('.picker-option')?.focus()
}
const clearSlot = async (side: ArenaTeamSide, index: number, fighter: ArenaSlotFighter) => {
  if (isOpponent(side)) props.match.clearCreature(creatureKeyOf(fighter.id))
  else if (fighter.is_robot) props.match.clearBot('B')
  else {
    const slot = teams.value.find((team) => team.side === side)?.slots[index]
    if (slot) props.match.clearFighter(slot)
  }
  await nextTick()
  document.getElementById(slotId(side, index))?.focus()
}
const imageFor = (fighter: ArenaSlotFighter) =>
  fighter.is_creature || fighter.is_robot
    ? getStaticImageUrl(getCreatureImagePath(creatureKeyOf(fighter.id)))
    : null
const actionFor = (fighter: ArenaSlotFighter) =>
  fighter.active_skill
    ? {
        name: fighter.active_skill.name,
        icon: fighter.active_skill.icon,
        charge: fighter.active_skill.charge,
        queued: fighter.active_skill.queued,
        pending: false,
        enabled: false,
      }
    : null
const pickerOptions = computed(() =>
  props.match.openPicker
    ? props.match
        .pickerOptions(props.match.openPicker)
        .filter((entry) => entry.name.toLowerCase().includes(search.value.toLowerCase().trim()))
    : []
)
const selectDweller = (entry: ArenaRosterEntry) => {
  if (props.match.openPicker) props.match.selectFighter(props.match.openPicker, entry)
  void closePickers()
}
const assignmentLabel = (entry: ArenaRosterEntry) =>
  entry.room_id === state.value?.room_id ||
  props.match.roster.some((dweller) => dweller.id === entry.id)
    ? 'In Arena'
    : entry.room_name
      ? `${entry.room_name} → Arena`
      : 'Available · joins Arena'
const selectOpponent = (creature: ArenaCreature) => {
  props.match.selectCreature(creature)
  void closePickers()
}
const emptySilhouetteUrl = getStaticImageUrl(
  '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp'
)
const modeLabel = computed(
  () =>
    props.match.modeOptions.find((option) => option.value === props.match.mode)?.label ?? 'Arena'
)
</script>

<template>
  <div class="arena-preview-shell relative w-full">
    <nav
      v-if="state && !match.isFighting"
      aria-label="Match mode"
      class="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4"
    >
      <Button
        variant="ghost"
        v-for="option in match.modeOptions"
        :key="option.value"
        type="button"
        class="h-auto min-w-0 flex-col items-start gap-1 whitespace-normal rounded-md border p-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
        :class="
          match.mode === option.value
            ? 'border-theme-primary bg-theme-primary/10 text-theme-primary'
            : 'border-theme-primary/20 text-muted-foreground hover:border-theme-primary hover:text-theme-primary'
        "
        :disabled="!match.canChangeFighters || !match.modeUnlocked(option.value)"
        :aria-pressed="match.mode === option.value"
        @click="match.selectMode(option.value)"
      >
        <span class="text-xs font-semibold">{{ option.label }}</span
        ><span class="text-[10px] leading-snug">{{
          match.modeUnlocked(option.value) ? option.description : `Unlocks at Tier ${option.tier}`
        }}</span>
      </Button>
    </nav>
    <ArenaRing
      v-if="match.isFighting && state"
      :state="state"
      :scene-image-url="sceneImageUrl"
      :skill-enabled="match.countdown === 0"
      :pending-skills="pendingSkills"
      :attacking-team="attackingTeam"
      :attacking-fighter-id="attackingFighterId"
      :damage-numbers="damageNumbers"
      :active-action="activeAction"
      :combat-phase="combatPhase"
      @skill="emit('skill', $event)"
    />
    <section
      v-else
      class="arena-preview relative isolate w-full min-w-0 overflow-hidden rounded-lg border border-theme-primary/30 bg-surface-sunken"
      aria-label="Arena preview"
    >
      <img
        v-if="scene"
        :src="scene"
        alt=""
        class="absolute inset-0 size-full object-cover"
        @error="imageFailed"
      />
      <div
        class="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-black/30"
      />
      <div
        class="absolute inset-x-4 top-3 flex justify-between text-xs font-semibold text-theme-primary"
      >
        <span>TEAM A</span
        ><span>{{
          match.mode === 'training' ? 'BOTS' : match.mode === 'hunt' ? 'CREATURES' : 'TEAM B'
        }}</span>
      </div>
      <div
        class="absolute inset-x-3 bottom-4 grid grid-cols-2 items-end gap-6 sm:inset-x-8 sm:bottom-6 sm:gap-12"
      >
        <div
          v-for="team in teams"
          :key="team.side"
          class="flex min-w-0 items-end justify-around gap-2"
          :class="{ 'flex-row-reverse': team.side === 'B' }"
        >
          <div
            v-for="(fighter, index) in team.fighters"
            :key="`${team.side}:${index}`"
            class="flex min-w-0 max-w-28 flex-1 flex-col items-center gap-1"
          >
            <template v-if="fighter">
              <CombatantMeters
                :name="fighter.name"
                :health="fighter.health"
                :max-health="fighter.max_health"
                :tone="team.side === 'A' ? 'success' : 'danger'"
                :action="actionFor(fighter)"
              />
              <Button
                variant="ghost"
                type="button"
                class="relative flex h-32 w-full shrink-0 items-end justify-center rounded p-0 hover:bg-transparent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary sm:h-44"
                :class="
                  !fighter.is_creature && !fighter.is_robot
                    ? `arena-body--${bodySizeFor(fighter)}`
                    : undefined
                "
                :disabled="!match.canChangeFighters"
                :id="slotId(team.side, index)"
                :aria-label="slotLabel(team.side, index)"
                @click="activateSlot(team.side, index)"
              >
                <img
                  v-if="imageFor(fighter)"
                  :src="imageFor(fighter) ?? undefined"
                  :alt="fighter.name"
                  class="size-full object-contain drop-shadow-lg"
                  :class="{ '-scale-x-100': team.side === 'B' && fighter.is_robot }"
                />
                <div
                  v-else-if="!fighter.is_creature && !fighter.is_robot"
                  class="size-full"
                  :class="{ '-scale-x-100': team.side === 'B' }"
                >
                  <DwellerPortrait
                    :image-url="fighter.image_url"
                    :thumbnail-url="fighter.thumbnail_url"
                    :alt="fighter.name"
                    :zoom="false"
                    image-class="size-full object-contain drop-shadow-lg"
                    ><template #fallback
                      ><span
                        class="arena-dweller-silhouette text-theme-primary/70"
                        :style="{
                          '--dweller-silhouette': emptySilhouetteUrl
                            ? `url('${emptySilhouetteUrl}')`
                            : 'none',
                        }" /></template
                  ></DwellerPortrait>
                </div>
                <PawPrint v-else class="size-12 text-theme-primary" />
              </Button>
              <div
                v-if="match.canChangeFighters"
                role="group"
                :aria-label="`Controls for ${fighter.name}`"
                class="flex h-8 items-center justify-center gap-1"
              >
                <Button
                  size="icon-sm"
                  class="size-7 sm:size-8"
                  variant="ghost"
                  :aria-label="`Change ${fighter.name}`"
                  :title="`Change ${fighter.name}`"
                  @click="activateSlot(team.side, index)"
                  ><ArrowLeftRight class="size-3.5"
                /></Button>
                <Button
                  size="icon-sm"
                  class="size-7 sm:size-8"
                  variant="ghost"
                  :aria-label="`Remove ${fighter.name} from fight`"
                  :title="`Remove ${fighter.name} from fight`"
                  @click="clearSlot(team.side, index, fighter)"
                  ><X class="size-3.5"
                /></Button>
              </div>
            </template>
            <Button
              variant="ghost"
              v-else
              type="button"
              class="arena-empty-slot flex h-auto w-full flex-col whitespace-normal p-0 items-center justify-end gap-1 rounded-md border border-dashed border-theme-primary/20 text-theme-primary/40 transition-colors hover:border-theme-primary hover:bg-theme-primary/5 hover:text-theme-primary focus-visible:text-theme-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary disabled:pointer-events-none disabled:opacity-40"
              :disabled="!match.canChangeFighters"
              :id="slotId(team.side, index)"
              :aria-label="slotLabel(team.side, index)"
              @click="activateSlot(team.side, index)"
            >
              <span class="relative flex h-32 w-full items-center justify-center sm:h-44"
                ><Bot
                  v-if="isOpponent(team.side) && match.mode === 'training'"
                  class="size-12" /><PawPrint
                  v-else-if="isOpponent(team.side)"
                  class="size-12" /><span
                  v-else
                  class="arena-dweller-silhouette"
                  :class="{ '-scale-x-100': team.side === 'B' }"
                  :style="{
                    '--dweller-silhouette': emptySilhouetteUrl
                      ? `url('${emptySilhouetteUrl}')`
                      : 'none',
                  }" /><Plus class="absolute bottom-1 right-1 size-4"
              /></span>
              <span class="pb-2 text-[9px] font-semibold">{{
                isOpponent(team.side)
                  ? match.mode === 'training'
                    ? 'Add bot'
                    : 'Add creature'
                  : 'Add dweller'
              }}</span>
            </Button>
          </div>
        </div>
      </div>
      <div
        v-if="match.stage === 'fight' && match.isDone"
        class="absolute inset-0 z-20 flex items-center justify-center bg-black/80 p-4 text-center"
      >
        <div class="result-banner flex flex-col items-center gap-2">
          <p class="text-sm font-bold text-theme-primary">
            {{ match.winnerName ? `${match.winnerName} wins!` : 'Match complete' }}
          </p>
          <p v-if="match.matchReward" class="max-w-md text-xs text-muted-foreground">
            {{ match.matchReward }}
          </p>
          <div class="flex flex-wrap justify-center gap-2">
            <Button :disabled="match.isStarting || !match.canStart" @click="match.rematch()">{{
              match.isStarting ? 'Starting…' : 'FIGHT AGAIN'
            }}</Button
            ><Button
              v-if="match.injuredFighters.length"
              variant="secondary"
              :disabled="match.isHealing"
              @click="match.healInjured()"
              >HEAL INJURED ({{ match.injuredFighters.length }})</Button
            ><Button variant="outline" @click="match.setStage('fighters')">CHANGE FIGHTERS</Button>
          </div>
        </div>
      </div>
    </section>
    <section
      v-if="match.openPicker"
      ref="fighterPicker"
      class="mt-3 rounded-lg border border-theme-primary/30 bg-surface-sunken p-3"
      aria-label="Choose fighter"
      @keydown.esc.prevent.stop="closePickers()"
    >
      <div class="mb-2 flex items-center justify-between gap-2">
        <label class="flex flex-1 flex-col gap-1 text-xs text-muted-foreground"
          >Choose a dweller<Input
            v-model="search"
            type="search"
            placeholder="Search dwellers…"
            class="h-9 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring" /></label
        ><Button
          size="icon-sm"
          variant="ghost"
          aria-label="Close fighter picker"
          @click="closePickers()"
          ><X
        /></Button>
      </div>
      <div class="grid max-h-64 gap-1 overflow-y-auto sm:grid-cols-2">
        <Button
          variant="ghost"
          v-for="entry in pickerOptions"
          :key="entry.id"
          type="button"
          class="picker-option flex h-auto justify-start whitespace-normal items-center gap-2 rounded border border-transparent p-2 text-left transition-colors hover:border-theme-primary/40 hover:bg-theme-primary/10 focus-visible:outline-2 focus-visible:outline-theme-primary"
          @click="selectDweller(entry)"
        >
          <DwellerPortrait
            :image-url="entry.image_url"
            :thumbnail-url="entry.thumbnail_url"
            :alt="entry.name"
            prefer-thumbnail
            image-class="size-9 shrink-0 rounded object-cover"
            fallback-class="size-9 shrink-0 text-theme-primary"
          /><span class="flex min-w-0 flex-col"
            ><span class="truncate text-xs">{{ entry.name }}</span
            ><span class="text-[10px] text-muted-foreground"
              >Lv {{ entry.level }} · {{ entry.health }} / {{ entry.max_health }} HP</span
            ><span class="text-[10px] text-theme-primary/80">{{
              assignmentLabel(entry)
            }}</span></span
          >
        </Button>
      </div>
      <p v-if="!pickerOptions.length" class="py-2 text-xs text-muted-foreground">
        No available adult dwellers match this selection.
      </p>
    </section>
    <section
      v-if="match.creaturePickerOpen"
      ref="opponentPicker"
      @keydown.esc.prevent.stop="closePickers()"
      class="mt-3 rounded-lg border border-theme-primary/30 bg-surface-sunken p-3"
      :aria-label="match.mode === 'training' ? 'Choose bot' : 'Choose creature'"
    >
      <div class="mb-2 flex items-center justify-between text-xs text-theme-primary">
        <span>{{ match.mode === 'training' ? 'Choose a training bot' : 'Choose a creature' }}</span
        ><Button
          size="icon-sm"
          variant="ghost"
          aria-label="Close creature picker"
          @click="closePickers()"
          ><X
        /></Button>
      </div>
      <div class="grid max-h-64 gap-1 overflow-y-auto sm:grid-cols-2">
        <Button
          variant="ghost"
          v-for="creature in match.creaturePickerOptions"
          :key="creature.key"
          type="button"
          class="picker-option flex h-auto justify-start whitespace-normal items-center gap-2 rounded border border-transparent p-2 text-left hover:border-theme-primary/40 hover:bg-theme-primary/10 focus-visible:outline-2 focus-visible:outline-theme-primary"
          @click="selectOpponent(creature)"
        >
          <img
            v-if="getCreatureImagePath(creature.key)"
            :src="getStaticImageUrl(getCreatureImagePath(creature.key)) ?? undefined"
            alt=""
            class="size-9 shrink-0 object-contain"
            :class="{ '-scale-x-100': creature.is_robot }"
          /><span class="flex flex-col text-xs"
            ><span>{{ creature.name }}</span
            ><span class="text-[10px] text-muted-foreground"
              >POW {{ Math.round(creature.power) }} · {{ creature.max_hp }} HP</span
            ></span
          >
        </Button>
      </div>
      <p v-if="!match.creaturePickerOptions.length" class="py-2 text-xs text-muted-foreground">
        No opponents available.
      </p>
    </section>
    <div
      v-if="state && !match.isFighting && match.stage === 'fighters'"
      class="mt-3 flex flex-col gap-3 rounded-lg border border-theme-primary/20 bg-surface-sunken p-3"
    >
      <div
        v-if="match.mode === 'hunt' && match.huntPresets.length"
        class="flex flex-wrap gap-2"
        aria-label="Hunt preset"
      >
        <Button
          v-for="preset in match.huntPresets"
          :key="preset.name"
          size="xs"
          variant="outline"
          :aria-pressed="match.selectedHuntPreset === preset.name"
          @click="match.selectHuntPreset(preset.name)"
          >{{ preset.name }}</Button
        >
      </div>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p role="status" class="text-xs text-muted-foreground">
          {{ match.canStart ? `${modeLabel} · Teams ready` : match.needsLabel }}
        </p>
        <Button :disabled="!match.canStart || match.isStarting" @click="match.startFight()">{{
          match.isStarting ? 'Starting…' : 'START FIGHT'
        }}</Button>
      </div>
      <p
        v-if="match.candidates.some((entry) => entry.room_id !== state?.room_id)"
        class="text-[10px] text-muted-foreground"
      >
        New fighters move to the Arena when the match starts.
      </p>
    </div>
    <div v-if="match.isFighting" class="mt-2 flex justify-end">
      <Button variant="destructive" size="sm" @click="emit('stop')">STOP FIGHT</Button>
    </div>
    <div
      v-if="skillBurst"
      :key="skillBurst.id"
      role="status"
      class="absolute inset-x-4 top-1/2 z-30 flex -translate-y-1/2 items-center justify-center gap-2 rounded border border-warning/40 bg-black/85 px-3 py-2 text-center text-xs font-semibold text-warning"
    >
      <CombatSkillIcon :icon="skillBurst.icon" class="size-5" />{{ skillBurst.message }}
    </div>
  </div>
</template>

<style scoped>
.arena-preview {
  min-height: 300px;
  aspect-ratio: 2 / 1;
}
.arena-dweller-silhouette {
  display: block;
  width: 100%;
  height: 8rem;
  background-color: currentColor;
  mask-image: var(--dweller-silhouette);
  mask-repeat: no-repeat;
  mask-position: center bottom;
  mask-size: contain;
  mask-mode: alpha;
}
.arena-body--large {
  height: 9.5rem;
}
.arena-body--small {
  height: 6.5rem;
}
@media (min-width: 640px) {
  .arena-dweller-silhouette {
    height: 11rem;
  }
  .arena-body--large {
    height: 13rem;
  }
  .arena-body--small {
    height: 9rem;
  }
}
</style>
