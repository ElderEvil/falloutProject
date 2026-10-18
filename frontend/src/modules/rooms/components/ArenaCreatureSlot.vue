<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { X } from '@lucide/vue'
import { Button } from '@/core/components/ui/button'
import type { ArenaCreature } from '../api/arena'
import type { ArenaCreatureView } from '../models/arena'
import { getCreatureImagePath } from '@/core/utils/creatureAssets'
import { getStaticImageUrl } from '@/core/utils/image'
import ArenaCombatantCard from './ArenaCombatantCard.vue'

interface Props {
  creature: ArenaCreatureView | null
  canChange: boolean
  options: ArenaCreature[]
  pickerOpen: boolean
  mirror?: boolean
  mirrorBots?: boolean
  friendly?: boolean
  emptyLabel?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  clear: [key: string]
  togglePicker: []
  select: [creature: ArenaCreature]
}>()

const powerLabel = computed(() => (props.creature ? Math.round(props.creature.power) : null))
const failedUrls = ref(new Set<string>())
const imageFor = (key: string) => {
  const url = getStaticImageUrl(getCreatureImagePath(key))
  return url && !failedUrls.value.has(url) ? url : null
}
const creatureImage = computed(() => (props.creature ? imageFor(props.creature.key) : null))
const pickerOptions = computed(() =>
  props.options.map((option) => ({ option, image: imageFor(option.key) }))
)
const onImageError = (event: Event) => failedUrls.value.add((event.target as HTMLImageElement).src)
</script>

<template>
  <div class="creature-slot relative flex h-full min-w-0 flex-col gap-2">
    <ArenaCombatantCard
      v-if="creature"
      class="creature-card"
      :name="creature.name"
      :power="powerLabel"
      :health="creature.health"
      :max-health="creature.max_health"
      :editable="canChange"
      :hostile="!friendly"
    >
      <template #portrait>
        <img
          v-if="creatureImage"
          :key="creatureImage"
          :src="creatureImage"
          :alt="creature.name"
          class="size-full object-contain p-0.5"
          :class="{ 'face-center': props.mirror || (props.mirrorBots && creature.is_robot) }"
          @error="onImageError"
        />
        <Icon v-else icon="mdi:paw" class="size-12 text-danger" />
      </template>
      <template #management>
        <Button
          size="icon-sm"
          variant="ghost"
          :aria-label="`Clear ${creature.name}`"
          @click="emit('clear', creature.key)"
          ><X class="size-4"
        /></Button>
      </template>
    </ArenaCombatantCard>
    <Button
      v-else
      variant="outline"
      class="creature-slot-empty h-auto min-h-20 w-full flex-1 flex-col gap-1 whitespace-normal border-dashed px-2 py-2 text-center"
      :disabled="!canChange || !options.length"
      :aria-expanded="pickerOpen"
      type="button"
      @click="emit('togglePicker')"
    >
      <span>{{ emptyLabel ?? '+ ADD CREATURE' }}</span>
    </Button>
    <div
      v-if="pickerOpen && canChange"
      class="picker flex max-h-48 flex-col gap-1 overflow-y-auto rounded-md border border-input bg-popover p-1"
    >
      <Button
        v-for="{ option, image } in pickerOptions"
        :key="option.key"
        variant="ghost"
        class="picker-option h-auto w-full justify-start gap-2 whitespace-normal px-2 py-2 text-left"
        type="button"
        @click="emit('select', option)"
      >
        <img
          v-if="image"
          :src="image"
          alt=""
          class="size-12 shrink-0 object-contain"
          :class="{ 'face-center': props.mirror || (props.mirrorBots && option.is_robot) }"
          @error="onImageError"
        />
        <Icon v-else icon="mdi:paw" class="size-12 shrink-0 text-danger" />
        <span class="flex min-w-0 flex-col">
          <span class="picker-name break-words text-danger">{{ option.name }}</span>
          <span class="picker-meta text-xs text-muted-foreground"
            >POW {{ Math.round(option.power) }} &middot; {{ option.max_hp }} HP</span
          >
        </span>
      </Button>
      <div v-if="!options.length" class="picker-empty p-2 text-xs text-muted-foreground">
        No creatures available.
      </div>
    </div>
  </div>
</template>

<style scoped>
.face-center {
  transform: scaleX(-1);
}
</style>
