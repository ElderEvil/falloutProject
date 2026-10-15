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

interface Props {
  side: ArenaSlotKey
  fighter: ArenaSlotFighter | null
  canChange: boolean
  damageNumbers: Array<{ id: number; amount: number }>
  options: ArenaRosterEntry[]
  pickerOpen: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  clear: [side: ArenaSlotKey]
  togglePicker: [side: ArenaSlotKey]
  select: [side: ArenaSlotKey, entry: ArenaRosterEntry]
}>()

const powerLabel = computed(() =>
  props.fighter?.power != null ? Math.round(props.fighter.power) : null
)

const healthPercent = (f: ArenaSlotFighter | null) =>
  f ? Math.round((f.health / Math.max(1, f.max_health)) * 100) : 0
</script>

<template>
  <div class="fighter-slot relative flex min-w-0 flex-col gap-2">
    <Card v-if="fighter" class="fighter-card relative gap-2 py-3" size="sm">
      <div class="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <span v-for="d in damageNumbers" :key="d.id" class="damage-number">-{{ d.amount }}</span>
      </div>
      <CardHeader class="justify-items-center text-center">
        <div
          class="fighter-portrait flex size-10 items-center justify-center overflow-hidden rounded-full border-2 border-theme-primary bg-surface-raised"
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
.damage-number {
  position: absolute;
  top: 10px;
  left: 50%;
  color: var(--color-danger);
  font-weight: bold;
  font-size: 0.95rem;
  animation: damage-float 0.9s ease-out forwards;
}
@keyframes damage-float {
  from {
    opacity: 1;
    transform: translate(-50%, 0);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -32px);
  }
}
@media (prefers-reduced-motion: reduce) {
  .damage-number {
    animation: none;
    transform: translateX(-50%);
  }
}
</style>
