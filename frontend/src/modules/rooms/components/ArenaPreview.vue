<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UserRound, PawPrint, Plus, X, ArrowLeftRight } from '@lucide/vue'
import { Button } from '@/core/components/ui/button'
import type { ArenaCreature, ArenaRosterEntry } from '../api/arena'
import {
  creatureKeyOf,
  type ArenaSlotFighter,
  type ArenaSlotKey,
  type ArenaTeamSide,
} from '../models/arena'
import { getCreatureImagePath } from '@/core/utils/creatureAssets'
import { getStaticImageUrl } from '@/core/utils/image'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { getDwellerBodySize } from '@/modules/dwellers/models/dweller'
import ArenaRing from './ArenaRing.vue'
import CombatantMeters from './CombatantMeters.vue'
import { useFallbackImage } from '../composables/useFallbackImage'
import type { ArenaMatchDraft, ArenaStage } from '../composables/useArenaMatchDraft'

interface Props {
  match: ArenaMatchDraft
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

const emit = defineEmits<{
  skill: [fighterId: string]
  stop: []
  assignDwellers: []
}>()

const { url: scene, onError: imageFailed } = useFallbackImage(() => [props.sceneImageUrl])

const state = computed(() => props.match.roomState)
const match = computed(() => props.match)
const stage = computed(() => props.match.stage)
const isFighting = computed(() => props.match.isFighting)

const teams = computed<
  Array<{
    side: ArenaTeamSide
    fighters: Array<ArenaSlotFighter | null>
    slots: readonly ArenaSlotKey[]
  }>
>(() => [
  { side: 'A', fighters: props.match.teamA, slots: props.match.slotKeysA },
  { side: 'B', fighters: props.match.teamB, slots: props.match.slotKeysB },
])

const slotKeyFor = (side: ArenaTeamSide, index: number): ArenaSlotKey | null =>
  teams.value.find((team) => team.side === side)?.slots[index] ?? null

const isCreatureSide = (side: ArenaTeamSide) => side === 'B' && props.match.mode === 'hunt'
const isBotSlot = (side: ArenaTeamSide, index: number) =>
  side === 'B' && props.match.mode === 'brawl' && index === 1 && props.match.botEnabled.B

const emptySilhouetteUrl = getStaticImageUrl(
  '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp'
)

const bodySizeFor = (fighter: ArenaSlotFighter) =>
  getDwellerBodySize({
    age_group: fighter.age_group,
    visual_attributes: fighter.race ? { race: fighter.race } : null,
  })
const bodySizeClass = (fighter: ArenaSlotFighter) => `arena-body--${bodySizeFor(fighter)}`
defineExpose({ bodySizeFor })

const actionFor = (fighter: ArenaSlotFighter) => {
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

const imageFor = (fighter: ArenaSlotFighter) =>
  fighter.is_creature || fighter.is_robot
    ? getStaticImageUrl(getCreatureImagePath(creatureKeyOf(fighter.id)))
    : null

const creatureImageFor = (key: string) => getStaticImageUrl(getCreatureImagePath(key))

const stageClass = (key: ArenaStage) =>
  props.match.stage === key
    ? 'bg-theme-primary text-black'
    : 'text-theme-primary/70 hover:bg-theme-primary/10 hover:text-theme-primary'

const stageDisabled = (key: ArenaStage) => props.match.isFighting && key !== 'fight'

const activateSlot = (side: ArenaTeamSide, index: number) => {
  if (!props.match.canChangeFighters) return
  if (isCreatureSide(side)) {
    props.match.toggleCreaturePicker(index)
    return
  }
  if (isBotSlot(side, index)) {
    props.match.toggleBotPicker('B')
    return
  }
  const slot = slotKeyFor(side, index)
  if (slot) props.match.togglePicker(slot)
}

const clearSlot = (side: ArenaTeamSide, index: number, fighter: ArenaSlotFighter) => {
  if (!props.match.canChangeFighters) return
  if (isCreatureSide(side)) {
    props.match.clearCreature(creatureKeyOf(fighter.id))
    return
  }
  if (isBotSlot(side, index)) {
    props.match.clearBot('B')
    return
  }
  const slot = slotKeyFor(side, index)
  if (slot) props.match.clearFighter(slot)
}

const slotLabel = (side: ArenaTeamSide, index: number) => {
  if (isCreatureSide(side)) return `Select creature ${index + 1} for Team B`
  if (isBotSlot(side, index)) return 'Select training bot for Team B'
  return `Select fighter for Team ${side}`
}

const currentPickerOptions = computed(() => {
  const slot = props.match.openPicker
  return slot ? props.match.pickerOptions(slot) : []
})

const currentPickerTitle = computed(() => {
  const slot = props.match.openPicker
  if (!slot) return ''
  return slot === 'a' || slot === 'c' ? 'Team A fighter' : 'Team B fighter'
})

const selectPickerEntry = (entry: ArenaRosterEntry) => {
  if (props.match.openPicker) props.match.selectFighter(props.match.openPicker, entry)
}

const creatureOptions = computed(() =>
  props.match.botPicker ? props.match.robotOptions : props.match.creaturePickerOptions
)
const creaturePickerTitle = computed(() => (props.match.botPicker ? 'Training bot' : 'Creature'))
const selectCreatureOption = (creature: ArenaCreature) => {
  if (props.match.botPicker) props.match.selectBot(props.match.botPicker, creature)
  else props.match.selectCreature(creature)
}
</script>

<template>
  <div class="arena-preview-shell relative w-full">
    <nav
      v-if="state"
      class="mb-2 flex items-center gap-1 rounded-md border border-theme-primary/20 bg-surface-sunken/80 p-1"
      aria-label="Arena stages"
    >
      <button
        v-for="step in match.stageOptions"
        :key="step.key"
        type="button"
        class="flex flex-1 items-center justify-center gap-1.5 rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors disabled:pointer-events-none disabled:opacity-40"
        :class="stageClass(step.key)"
        :disabled="stageDisabled(step.key)"
        :aria-current="stage === step.key ? 'step' : undefined"
        @click="match.setStage(step.key)"
      >
        <span
          class="flex size-4 items-center justify-center rounded-full border border-current text-[9px]"
          >{{ step.index }}</span
        >
        {{ step.label }}
      </button>
      <span
        class="ml-1 hidden shrink-0 rounded border border-theme-primary/30 px-1.5 py-0.5 text-[9px] font-semibold tracking-wider text-theme-primary sm:inline-flex"
        >{{ match.statusLabel }}</span
      >
    </nav>

    <ArenaRing
      v-if="isFighting && state"
      :state="state"
      :scene-image-url="sceneImageUrl"
      :skill-enabled="match.countdown === 0"
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

      <div
        v-if="stage === 'mode'"
        class="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-black/75 p-4"
      >
        <p class="text-xs font-semibold uppercase tracking-wider text-theme-primary">
          Choose match mode
        </p>
        <div class="grid w-full max-w-2xl gap-2 sm:grid-cols-3">
          <button
            v-for="option in match.modeOptions"
            :key="option.value"
            type="button"
            class="mode-option flex flex-col gap-1 rounded-lg border px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            :class="
              match.mode === option.value
                ? 'border-theme-primary bg-theme-primary/15'
                : 'border-theme-primary/30 bg-black/50 hover:border-theme-primary'
            "
            :disabled="!match.modeUnlocked(option.value)"
            :aria-pressed="match.mode === option.value"
            @click="match.selectMode(option.value)"
          >
            <span
              class="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wider text-theme-primary"
            >
              {{ option.label }}
              <Icon
                v-if="!match.modeUnlocked(option.value)"
                icon="mdi:lock-outline"
                class="size-3.5"
              />
            </span>
            <span class="text-[10px] leading-snug text-muted-foreground">{{
              option.description
            }}</span>
            <span v-if="!match.modeUnlocked(option.value)" class="text-[10px] text-warning"
              >Unlocks at Tier {{ option.tier }}</span
            >
            <span
              v-else-if="match.mode === option.value"
              class="text-[10px] font-semibold text-theme-primary"
              >SELECTED</span
            >
          </button>
        </div>
      </div>

      <template v-else>
        <span
          class="team-label absolute left-4 top-3 z-10 text-xs font-semibold tracking-wider text-theme-primary"
        >
          TEAM A
        </span>
        <span
          class="team-label absolute right-4 top-3 z-10 text-xs font-semibold tracking-wider text-theme-primary"
        >
          {{ match.mode === 'hunt' ? 'CREATURES' : 'TEAM B' }}
        </span>

        <div
          v-if="stage === 'fighters' && match.roster.length < match.requiredRosterSize"
          class="absolute left-1/2 top-10 z-20 flex -translate-x-1/2 items-center gap-2 rounded border border-warning/40 bg-black/80 px-2 py-1"
        >
          <span class="text-[10px] text-warning">
            Assign {{ match.requiredRosterSize - match.roster.length }} more adult{{
              match.requiredRosterSize - match.roster.length === 1 ? '' : 's'
            }}.
          </span>
          <Button size="xs" variant="outline" @click="emit('assignDwellers')">ASSIGN</Button>
        </div>

        <div
          class="absolute inset-x-3 bottom-5 grid grid-cols-2 items-end gap-8 sm:inset-x-8 sm:bottom-8 sm:gap-16"
        >
          <div
            v-for="team in teams"
            :key="team.side"
            class="flex min-w-0 items-end justify-around gap-2"
            :class="{ 'flex-row-reverse': team.side === 'B' }"
          >
            <div
              v-for="(fighter, index) in team.fighters"
              :key="fighter?.id ?? `${team.side}-${index}`"
              class="flex min-w-0 max-w-28 flex-1 flex-col items-center gap-1"
              :class="{
                'fighter-slot': !isCreatureSide(team.side) && !isBotSlot(team.side, index),
                'creature-slot': isCreatureSide(team.side) || isBotSlot(team.side, index),
              }"
            >
              <div
                v-if="
                  team.side === 'B' &&
                  match.mode === 'brawl' &&
                  index === 1 &&
                  stage === 'fighters' &&
                  match.canChangeFighters
                "
                class="mb-1 flex items-center justify-center gap-1"
                role="group"
                aria-label="Team B partner"
              >
                <button
                  type="button"
                  class="rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider transition-colors"
                  :class="
                    match.botEnabled.B
                      ? 'text-theme-primary/60 hover:text-theme-primary'
                      : 'bg-theme-primary text-black'
                  "
                  :aria-pressed="!match.botEnabled.B"
                  @click="match.choosePartnerType('B', false)"
                >
                  Dweller
                </button>
                <button
                  type="button"
                  class="rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider transition-colors"
                  :class="
                    match.botEnabled.B
                      ? 'bg-theme-primary text-black'
                      : 'text-theme-primary/60 hover:text-theme-primary'
                  "
                  :aria-pressed="match.botEnabled.B"
                  @click="match.choosePartnerType('B', true)"
                >
                  Bot
                </button>
              </div>

              <template v-if="fighter">
                <CombatantMeters
                  :name="fighter.name"
                  :health="fighter.health"
                  :max-health="fighter.max_health"
                  :tone="team.side === 'A' ? 'success' : 'danger'"
                  :action="actionFor(fighter)"
                />
                <div
                  class="relative flex h-32 w-full shrink-0 items-end justify-center sm:h-44"
                  :class="
                    !fighter.is_creature && !fighter.is_robot ? bodySizeClass(fighter) : undefined
                  "
                >
                  <img
                    v-if="imageFor(fighter)"
                    :src="imageFor(fighter) ?? undefined"
                    :alt="fighter.name"
                    class="size-full object-contain drop-shadow-lg"
                    :class="{ '-scale-x-100': team.side === 'B' && fighter.is_robot }"
                  />
                  <DwellerPortrait
                    v-else-if="!fighter.is_creature && !fighter.is_robot"
                    :image-url="fighter.image_url"
                    :thumbnail-url="fighter.thumbnail_url"
                    :alt="fighter.name"
                    :class="{ '-scale-x-100': team.side === 'B' }"
                    object-position="center top"
                    :zoom="false"
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
                    :class="{ '-scale-x-100': team.side === 'B' }"
                  />
                  <button
                    v-if="stage === 'fighters' && match.canChangeFighters"
                    type="button"
                    class="absolute inset-0 z-10 rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
                    :aria-label="slotLabel(team.side, index)"
                    @click="activateSlot(team.side, index)"
                  />
                  <div
                    v-if="stage === 'fighters' && match.canChangeFighters"
                    class="absolute right-0 top-0 z-20 flex gap-0.5"
                  >
                    <Button
                      v-if="!isCreatureSide(team.side) && !isBotSlot(team.side, index)"
                      size="icon-xs"
                      variant="outline"
                      :aria-label="`Swap ${fighter.name}`"
                      :title="`Swap ${fighter.name}`"
                      @click.stop="activateSlot(team.side, index)"
                    >
                      <ArrowLeftRight class="size-3" />
                    </Button>
                    <Button
                      size="icon-xs"
                      variant="ghost"
                      :aria-label="`Clear ${fighter.name}`"
                      :title="`Clear ${fighter.name}`"
                      @click.stop="clearSlot(team.side, index, fighter)"
                    >
                      <X class="size-3" />
                    </Button>
                  </div>
                </div>
              </template>

              <button
                v-else
                type="button"
                class="arena-empty-slot w-full flex-col disabled:pointer-events-none disabled:opacity-60"
                :class="{
                  'fighter-slot-empty': !isCreatureSide(team.side) && !isBotSlot(team.side, index),
                  'creature-slot-empty': isCreatureSide(team.side) || isBotSlot(team.side, index),
                }"
                :aria-label="slotLabel(team.side, index)"
                :disabled="!match.canChangeFighters"
                @click="activateSlot(team.side, index)"
              >
                <template v-if="isCreatureSide(team.side) || isBotSlot(team.side, index)">
                  <Icon
                    v-if="isBotSlot(team.side, index)"
                    icon="mdi:robot-outline"
                    class="size-12 text-theme-primary"
                  />
                  <PawPrint v-else class="size-12 text-danger" />
                  <span
                    class="text-[9px] font-semibold uppercase tracking-wider"
                    :class="isBotSlot(team.side, index) ? 'text-theme-primary' : 'text-danger'"
                  >
                    {{ isBotSlot(team.side, index) ? 'Add bot' : 'Add creature' }}
                  </span>
                </template>
                <template v-else>
                  <span
                    class="arena-dweller-silhouette"
                    :style="{
                      '--dweller-silhouette': emptySilhouetteUrl
                        ? `url('${emptySilhouetteUrl}')`
                        : 'none',
                    }"
                  />
                  <Plus class="arena-empty-plus" />
                </template>
              </button>
            </div>
          </div>
        </div>

        <div
          v-if="stage === 'fight'"
          class="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-black/75 p-4 text-center"
        >
          <span class="text-xs font-semibold uppercase tracking-wider text-theme-primary">
            {{ match.mode.toUpperCase() }} · {{ match.statusLabel }}
          </span>
          <template v-if="match.isDone">
            <div class="result-banner flex flex-col items-center gap-2">
              <p class="text-sm font-bold text-theme-primary">
                {{ match.winnerName ? `${match.winnerName} wins!` : 'Match complete' }}
              </p>
              <p v-if="match.matchReward" class="max-w-md text-xs text-muted-foreground">
                {{ match.matchReward }}
              </p>
              <div class="flex flex-wrap justify-center gap-2">
                <Button :disabled="match.isStarting" @click="match.rematch()">
                  <Icon v-if="match.isStarting" icon="mdi:loading" class="animate-spin" />
                  <Icon v-else icon="mdi:sword-cross" />
                  FIGHT AGAIN
                </Button>
                <Button variant="outline" @click="match.setStage('fighters')"
                  >CHANGE FIGHTERS</Button
                >
              </div>
            </div>
          </template>
          <template v-else>
            <p class="max-w-md text-xs text-muted-foreground">
              {{
                match.canStart
                  ? 'Both sides are ready. Start the match when you are.'
                  : match.needsLabel
              }}
            </p>
            <div class="flex flex-wrap justify-center gap-2">
              <Button :disabled="!match.canStart || match.isStarting" @click="match.startFight()">
                <Icon v-if="match.isStarting" icon="mdi:loading" class="animate-spin" />
                <Icon v-else icon="mdi:sword-cross" />
                START FIGHT
              </Button>
              <Button variant="outline" @click="match.setStage('fighters')">CHANGE FIGHTERS</Button>
              <Button
                v-if="match.roster.length < match.requiredRosterSize"
                variant="outline"
                @click="emit('assignDwellers')"
                >ASSIGN DWELLERS</Button
              >
            </div>
          </template>
        </div>

        <div
          v-if="match.openPicker"
          class="absolute inset-x-3 bottom-3 z-30 max-h-[55%] overflow-y-auto rounded-lg border border-theme-primary/40 bg-popover/95 p-2 shadow-xl backdrop-blur"
        >
          <div class="mb-1 flex items-center justify-between">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-theme-primary">
              {{ currentPickerTitle }}
            </span>
            <Button
              size="icon-xs"
              variant="ghost"
              aria-label="Close fighter picker"
              @click="match.closePickers()"
            >
              <X class="size-3" />
            </Button>
          </div>
          <div class="grid gap-1 sm:grid-cols-2">
            <button
              v-for="entry in currentPickerOptions"
              :key="entry.id"
              type="button"
              class="picker-option flex items-center gap-2 rounded border border-transparent px-2 py-1.5 text-left transition-colors hover:border-theme-primary/40 hover:bg-theme-primary/10"
              @click="selectPickerEntry(entry)"
            >
              <DwellerPortrait
                :image-url="entry.image_url"
                :thumbnail-url="entry.thumbnail_url"
                :alt="entry.name"
                prefer-thumbnail
                image-class="size-9 shrink-0 rounded object-cover"
                fallback-class="size-9 shrink-0 text-theme-primary"
              />
              <span class="flex min-w-0 flex-col">
                <span class="truncate text-xs">{{ entry.name }}</span>
                <span class="text-[10px] text-muted-foreground"
                  >Lv {{ entry.level }} · {{ entry.health }} / {{ entry.max_health }} HP</span
                >
              </span>
            </button>
          </div>
          <p v-if="!currentPickerOptions.length" class="p-2 text-xs text-muted-foreground">
            No other assigned adults available. Assign more dwellers to the Arena first.
          </p>
        </div>

        <div
          v-if="match.creaturePickerOpen || match.botPicker"
          class="absolute inset-x-3 bottom-3 z-30 max-h-[55%] overflow-y-auto rounded-lg border border-theme-primary/40 bg-popover/95 p-2 shadow-xl backdrop-blur"
        >
          <div class="mb-1 flex items-center justify-between">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-theme-primary">
              {{ creaturePickerTitle }}
            </span>
            <Button
              size="icon-xs"
              variant="ghost"
              aria-label="Close creature picker"
              @click="match.closePickers()"
            >
              <X class="size-3" />
            </Button>
          </div>
          <div class="grid gap-1 sm:grid-cols-2">
            <button
              v-for="creature in creatureOptions"
              :key="creature.key"
              type="button"
              class="picker-option flex items-center gap-2 rounded border border-transparent px-2 py-1.5 text-left transition-colors hover:border-theme-primary/40 hover:bg-theme-primary/10"
              @click="selectCreatureOption(creature)"
            >
              <img
                v-if="creatureImageFor(creature.key)"
                :src="creatureImageFor(creature.key) ?? undefined"
                alt=""
                class="size-9 shrink-0 object-contain"
                :class="{ '-scale-x-100': creature.is_robot }"
              />
              <Icon v-else icon="mdi:paw" class="size-9 shrink-0 text-danger" />
              <span class="flex min-w-0 flex-col">
                <span class="truncate text-xs text-danger">{{ creature.name }}</span>
                <span class="text-[10px] text-muted-foreground"
                  >POW {{ Math.round(creature.power) }} · {{ creature.max_hp }} HP</span
                >
              </span>
            </button>
          </div>
          <p v-if="!creatureOptions.length" class="p-2 text-xs text-muted-foreground">
            No creatures available.
          </p>
        </div>
      </template>
    </section>

    <div
      v-if="state && !isFighting && stage === 'fighters'"
      class="mt-2 flex flex-col gap-3 rounded-lg border border-theme-primary/20 bg-surface-sunken p-3"
    >
      <div
        v-if="
          match.mode === 'hunt' &&
          match.huntPresets.length &&
          match.canChangeFighters &&
          match.roster.length >= match.requiredRosterSize
        "
        class="flex flex-wrap items-center gap-2"
        aria-label="Hunt preset"
      >
        <button
          v-for="preset in match.huntPresets"
          :key="preset.name"
          type="button"
          class="rounded border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors"
          :class="
            match.selectedHuntPreset === preset.name
              ? 'border-theme-primary bg-theme-primary/15 text-theme-primary'
              : 'border-theme-primary/30 bg-black/50 text-muted-foreground hover:border-theme-primary hover:text-theme-primary'
          "
          :aria-pressed="match.selectedHuntPreset === preset.name"
          @click="match.selectHuntPreset(preset.name)"
        >
          {{ preset.name }}
        </button>
        <span v-if="match.opponentKeys.length" class="text-[10px] text-muted-foreground"
          >POW {{ match.opponentPower }}</span
        >
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3">
        <p role="status" class="text-xs text-muted-foreground">
          {{
            match.canStart ? 'Teams ready. Review your match before starting.' : match.needsLabel
          }}
        </p>
        <Button :disabled="!match.canStart" @click="match.setStage('fight')">
          Review fight
          <Icon icon="mdi:arrow-right" />
        </Button>
      </div>
    </div>

    <div v-if="isFighting" class="mt-2 flex justify-end">
      <Button variant="destructive" size="sm" @click="emit('stop')">STOP FIGHT</Button>
    </div>

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

.arena-body--large {
  height: 9.5rem;
}

.arena-body--small {
  height: 6.5rem;
}

@media (min-width: 640px) {
  .arena-body--large {
    height: 13rem;
  }

  .arena-body--small {
    height: 9rem;
  }
}
</style>
