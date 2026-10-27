<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  rooms: string[]
  current: number
  status?: string
}

const props = withDefaults(defineProps<Props>(), {
  status: 'in_room',
})

const isComplete = (index: number) =>
  index < props.current || (props.status === 'cleared' && index === props.current)

const isCurrent = (index: number) => index === props.current && props.status !== 'cleared'

const stepClass = (index: number) => {
  if (isComplete(index)) return 'border-theme-primary/40 bg-theme-primary/15 text-theme-primary'
  if (isCurrent(index)) return 'border-theme-primary bg-theme-primary text-surface-sunken'
  return 'border-theme-primary/25 text-theme-primary/50'
}

const labelClass = (index: number) => {
  if (isCurrent(index)) return 'text-theme-primary'
  if (isComplete(index)) return 'text-theme-primary/60'
  return 'text-theme-primary/40'
}
</script>

<template>
  <ol class="flex items-center gap-1.5 overflow-x-auto pb-1" aria-label="Room progress">
    <li v-for="(room, index) in rooms" :key="index" class="flex min-w-0 items-center gap-1.5">
      <span
        class="flex size-6 shrink-0 items-center justify-center rounded-full border text-[0.6875rem] font-bold"
        :class="stepClass(index)"
        :aria-current="isCurrent(index) ? 'step' : undefined"
        :title="room"
      >
        <Icon v-if="isComplete(index)" icon="mdi:check" class="h-3.5 w-3.5" />
        <span v-else>{{ index + 1 }}</span>
      </span>
      <span class="hidden max-w-28 truncate text-xs font-semibold sm:inline" :class="labelClass(index)">
        {{ room }}
      </span>
      <span
        v-if="index < rooms.length - 1"
        class="h-px w-3 shrink-0 bg-theme-primary/25"
        aria-hidden="true"
      />
    </li>
  </ol>
</template>
