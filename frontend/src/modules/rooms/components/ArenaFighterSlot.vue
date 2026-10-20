<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { ArrowLeftRight, X } from '@lucide/vue'
import { Button } from '@/core/components/ui/button'
import type { ArenaRosterEntry } from '../api/arena'
import type { ArenaSlotFighter, ArenaSlotKey } from '../models/arena'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import ArenaCombatantCard from './ArenaCombatantCard.vue'

interface Props {
  side: ArenaSlotKey
  fighter: ArenaSlotFighter | null
  canChange: boolean
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
</script>

<template>
  <div class="fighter-slot relative flex h-full min-w-0 flex-col gap-2">
    <ArenaCombatantCard
      v-if="fighter"
      class="fighter-card"
      :name="fighter.name"
      :subtitle="`Lv ${fighter.level}`"
      :power="powerLabel"
      :health="fighter.health"
      :max-health="fighter.max_health"
      :editable="canChange"
    >
      <template #portrait>
        <DwellerPortrait
          :image-url="fighter.image_url"
          :thumbnail-url="fighter.thumbnail_url"
          :alt="fighter.name"
          prefer-thumbnail
          image-class="size-full object-contain"
          fallback-class="size-12 text-theme-primary"
        />
      </template>
      <template #management>
        <Button
          variant="outline"
          size="icon-sm"
          :aria-label="`Swap ${fighter.name}`"
          :title="`Swap ${fighter.name}`"
          :aria-expanded="pickerOpen"
          @click="emit('togglePicker', side)"
          ><ArrowLeftRight class="size-4"
        /></Button>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label="Clear fighter"
          @click="emit('clear', side)"
        >
          <X class="size-4" />
        </Button>
      </template>
    </ArenaCombatantCard>
    <template v-else>
      <Button
        class="fighter-slot-empty h-auto min-h-20 w-full flex-1 flex-col gap-1 whitespace-normal border-dashed px-2 py-2 text-center"
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
          image-class="size-12 shrink-0 rounded-md object-cover"
          fallback-class="size-12 shrink-0 text-theme-primary"
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
