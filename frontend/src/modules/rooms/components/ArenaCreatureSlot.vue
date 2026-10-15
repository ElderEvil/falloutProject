<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import type { ArenaCreature } from '../api/arena'
import type { ArenaCreatureView } from '../models/arena'
import { getCreatureImagePath } from '@/core/utils/creatureAssets'
import { getStaticImageUrl } from '@/core/utils/image'
import ArenaDamageNumbers from './ArenaDamageNumbers.vue'

interface Props {
  creature: ArenaCreatureView | null
  canChange: boolean
  damageNumbers: Array<{ id: number; amount: number }>
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

const healthPercent = (creature: ArenaCreatureView | null) =>
  creature ? Math.round((creature.health / Math.max(1, creature.max_health)) * 100) : 0
</script>

<template>
  <div class="creature-slot">
    <div v-if="creature" class="creature-card">
      <TooltipProvider v-if="canChange" :delay-duration="200">
        <Tooltip>
          <TooltipTrigger as-child>
            <Button
              class="slot-clear"
              size="icon-lg"
              variant="destructive"
              :aria-label="`Clear ${creature.name}`"
              @click="emit('clear', creature.key)"
            >
              <Icon icon="mdi:close" class="size-5 text-danger" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Clear creature</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <ArenaDamageNumbers :numbers="damageNumbers" />
      <div
        class="flex h-28 w-full items-center justify-center rounded-lg border bg-surface-raised"
        :class="friendly ? 'border-theme-primary' : 'border-danger'"
      >
        <img
          v-if="creatureImage"
          :key="creatureImage"
          :src="creatureImage"
          :alt="creature.name"
          class="h-full w-full object-contain p-2"
          :class="{ 'face-center': props.mirror || (props.mirrorBots && creature.is_robot) }"
          @error="onImageError"
        />
        <Icon v-else icon="mdi:paw" class="h-10 w-10 text-danger" />
      </div>
      <div class="creature-name" :class="friendly ? 'text-theme-primary' : 'text-danger'">
        {{ creature.name }}
      </div>
      <div class="creature-meta">POW {{ powerLabel }}</div>
      <div class="hp-track">
        <Progress :model-value="healthPercent(creature)" class="h-2.5" />
      </div>
      <div class="hp-text">{{ creature.health }}/{{ creature.max_health }}</div>
    </div>
    <Button
      v-else
      variant="ghost"
      class="creature-slot-empty"
      type="button"
      @click="emit('togglePicker')"
    >
      <span>{{ emptyLabel ?? '+ ADD CREATURE' }}</span>
    </Button>
    <div v-if="pickerOpen && canChange" class="picker">
      <Button
        v-for="{ option, image } in pickerOptions"
        :key="option.key"
        variant="ghost"
        class="picker-option"
        type="button"
        @click="emit('select', option)"
      >
        <img
          v-if="image"
          :src="image"
          alt=""
          class="h-10 w-10 shrink-0 object-contain"
          :class="{ 'face-center': props.mirror || (props.mirrorBots && option.is_robot) }"
          @error="onImageError"
        />
        <Icon v-else icon="mdi:paw" class="h-10 w-10 shrink-0 text-danger" />
        <span class="flex min-w-0 flex-col">
          <span class="picker-name">{{ option.name }}</span>
          <span class="picker-meta"
            >POW {{ Math.round(option.power) }} &middot; {{ option.max_hp }} HP</span
          >
        </span>
      </Button>
      <div v-if="!options.length" class="picker-empty">No creatures available.</div>
    </div>
  </div>
</template>

<style scoped>
.creature-slot {
  position: relative;
  display: flex;
  flex-direction: column;
}

.face-center {
  transform: scaleX(-1);
}

.slot-clear {
  position: absolute;
  top: 4px;
  right: 6px;
  z-index: 3;
}

.creature-slot-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  padding: 1rem;
  border: 1px dashed var(--color-surface-hover);
  border-radius: 8px;
  background: transparent;
  color: var(--color-gray-500);
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 0.05em;
  cursor: pointer;
}

.creature-slot-empty:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
  background: transparent;
}

.picker {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 10;
  margin-top: 0.25rem;
  max-height: 160px;
  overflow-y: auto;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-surface-hover);
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.picker-option {
  display: flex;
  flex-direction: row;
  gap: 0.5rem;
  width: 100%;
  height: auto;
  align-items: center;
  border: 0;
  border-radius: 0;
  background: transparent;
  text-align: left;
  font-weight: normal;
  white-space: normal;
  padding: 0.45rem 0.6rem;
  cursor: pointer;
}

.picker-option:hover {
  background: var(--color-surface-hover);
}

.picker-name {
  font-size: 0.8rem;
  color: var(--color-danger);
}

.picker-meta {
  font-size: 0.65rem;
  color: var(--color-gray-400);
}

.picker-empty {
  padding: 0.6rem;
  font-size: 0.7rem;
  color: var(--color-gray-500);
}

.creature-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 3.25rem 1rem 1rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 8px;
}

.creature-name {
  font-weight: 600;
  text-align: center;
}

.creature-meta {
  font-size: 0.7rem;
  color: var(--color-gray-400);
}

.hp-track {
  width: 100%;
}

.hp-text {
  font-size: 0.7rem;
  color: var(--color-gray-400);
}
</style>
