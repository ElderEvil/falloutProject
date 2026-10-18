<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'
import type { ArenaRosterEntry } from '../api/arena'
import type { ArenaSlotFighter, ArenaSlotKey } from '../models/arena'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import ArenaDamageNumbers from './ArenaDamageNumbers.vue'

interface Props {
  side: ArenaSlotKey
  fighter: ArenaSlotFighter | null
  canChange: boolean
  damageNumbers: Array<{ id: number; amount: number }>
  options: ArenaRosterEntry[]
  pickerOpen: boolean
  skillEnabled?: boolean
  skillPending?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  skill: [fighterId: string]
  clear: [side: ArenaSlotKey]
  togglePicker: [side: ArenaSlotKey]
  select: [side: ArenaSlotKey, entry: ArenaRosterEntry]
}>()

const skill = computed(() => props.fighter?.active_skill)
const skillReady = computed(() => !!skill.value && skill.value.charge >= 100 && !skill.value.queued)
const canUseSkill = computed(
  () =>
    props.skillEnabled &&
    skillReady.value &&
    !props.skillPending &&
    (props.fighter?.health ?? 0) > 0
)

const powerLabel = computed(() =>
  props.fighter?.power != null ? Math.round(props.fighter.power) : null
)

const healthPercent = (f: ArenaSlotFighter | null) =>
  f ? Math.round((f.health / Math.max(1, f.max_health)) * 100) : 0
</script>

<template>
  <div class="fighter-slot relative flex min-w-0 flex-col gap-2">
    <Card v-if="fighter" class="fighter-card relative gap-2 py-3" size="sm">
      <ArenaDamageNumbers :numbers="damageNumbers" />
      <CardHeader class="justify-items-center text-center">
        <div
          :class="{ 'fighter-hit': damageNumbers.length > 0, 'fighter-channel': skill?.queued }"
          class="fighter-portrait flex size-14 items-center justify-center overflow-hidden rounded-full border-2 border-theme-primary bg-surface-raised"
        >
          <DwellerPortrait
            :image-url="fighter.image_url"
            :thumbnail-url="fighter.thumbnail_url"
            :alt="fighter.name"
            prefer-thumbnail
            image-class="size-full rounded-full object-cover"
            fallback-class="size-8 text-theme-primary"
          />
        </div>
        <CardTitle class="mt-1 max-w-full break-words">{{ fighter.name }}</CardTitle>
        <CardDescription class="flex flex-wrap justify-center gap-x-2 gap-y-1">
          <span class="whitespace-nowrap">Lv {{ fighter.level }}</span>
          <span v-if="powerLabel !== null" class="whitespace-nowrap">POW {{ powerLabel }}</span>
        </CardDescription>
      </CardHeader>
      <CardContent class="flex flex-col gap-1">
        <Progress :model-value="healthPercent(fighter)" :label="`${fighter.name} health`" />
        <span class="text-center text-xs text-muted-foreground tabular-nums"
          >{{ fighter.health }}/{{ fighter.max_health }}</span
        >
      </CardContent>
      <div v-if="skill" class="flex flex-col gap-1 px-3">
        <Button
          size="xs"
          :variant="skillReady && skillEnabled ? 'default' : 'outline'"
          :disabled="!canUseSkill"
          :aria-label="`Use ${skill.name} for ${fighter.name}`"
          :title="skill.description"
          :aria-describedby="`arena-skill-${fighter.id}`"
          class="h-auto min-h-9 w-full min-w-0 gap-1.5 px-2 py-1"
          :class="{ 'skill-ready': canUseSkill }"
          @click="emit('skill', fighter.id)"
        >
          <Icon
            icon="mdi:lightning-bolt"
            class="hidden size-3.5 shrink-0 sm:inline"
            :ariaHidden="true"
          />
          <span class="whitespace-normal">{{ skill.name }}</span>
        </Button>
        <div class="flex items-center gap-1.5">
          <Progress
            :model-value="skill.charge"
            :label="`${fighter.name} skill charge`"
            size="xs"
            tone="warning"
            class="flex-1"
          />
          <span class="shrink-0 text-[10px] tabular-nums text-muted-foreground">{{
            skill.queued || skillPending ? 'QUEUED' : skillReady ? 'READY' : `${skill.charge}%`
          }}</span>
        </div>
        <span :id="`arena-skill-${fighter.id}`" class="sr-only">{{ skill.description }}</span>
      </div>
      <CardFooter v-if="canChange" class="flex flex-wrap justify-center gap-1">
        <Button variant="outline" size="xs" @click="emit('togglePicker', side)">SWAP</Button>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label="Clear fighter"
          @click="emit('clear', side)"
        >
          <Icon icon="mdi:close" />
        </Button>
      </CardFooter>
    </Card>
    <template v-else>
      <Button
        class="fighter-slot-empty h-auto min-h-24 w-full flex-col gap-2 whitespace-normal border-dashed px-2 py-4 text-center"
        variant="outline"
        :disabled="!canChange || !options.length"
        :aria-expanded="pickerOpen"
        @click="emit('togglePicker', side)"
      >
        <Icon icon="mdi:account-outline" />
        Choose from roster
      </Button>
      <p v-if="canChange && !options.length" class="text-center text-xs text-muted-foreground">
        No other assigned adults available.
      </p>
    </template>
    <div
      v-if="pickerOpen && canChange"
      class="picker flex max-h-48 flex-col gap-1 overflow-y-auto rounded-md border border-input bg-popover p-1"
    >
      <Button
        v-for="entry in options"
        :key="entry.id"
        class="picker-option h-auto w-full justify-start gap-2 whitespace-normal px-2 py-2 text-left"
        variant="ghost"
        @click="emit('select', side, entry)"
      >
        <DwellerPortrait
          :image-url="entry.image_url"
          :thumbnail-url="entry.thumbnail_url"
          :alt="entry.name"
          prefer-thumbnail
          image-class="size-8 shrink-0 rounded-md object-cover"
          fallback-class="size-8 shrink-0 text-theme-primary"
        />
        <span class="flex min-w-0 flex-col gap-0.5">
          <span class="break-words">{{ entry.name }}</span>
          <span class="text-xs text-muted-foreground"
            >Lv {{ entry.level }} &middot; {{ entry.health }} / {{ entry.max_health }} HP</span
          >
        </span>
      </Button>
      <p v-if="!options.length" class="p-2 text-xs text-muted-foreground">
        No other assigned adults available. Assign more dwellers to the Arena first.
      </p>
    </div>
  </div>
</template>

<style scoped>
.fighter-hit {
  animation: fighter-impact 0.4s ease-out;
}
.fighter-channel {
  animation: fighter-channel 0.6s ease-in-out infinite alternate;
}
.skill-ready {
  animation: skill-ready 1.6s ease-in-out infinite alternate;
}
@keyframes fighter-impact {
  15%,
  45% {
    transform: translateX(-5px) rotate(-4deg);
    filter: brightness(1.8);
  }
  30%,
  60% {
    transform: translateX(5px) rotate(4deg);
  }
  to {
    transform: none;
    filter: none;
  }
}
@keyframes fighter-channel {
  to {
    box-shadow: 0 0 20px var(--color-warning);
    transform: scale(1.06);
  }
}
@keyframes skill-ready {
  to {
    box-shadow: 0 0 12px var(--color-theme-primary);
  }
}
@media (prefers-reduced-motion: reduce) {
  .fighter-hit,
  .fighter-channel,
  .skill-ready {
    animation: none;
  }
}
</style>
