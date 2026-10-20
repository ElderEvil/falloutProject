<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import { ROOM_STYLES, type RoomStyleValue } from '../models/room'

const props = defineProps<{
  modelValue: RoomStyleValue
  themes: RoomStyleValue[]
  tier: number
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: RoomStyleValue]
}>()

const options = computed(() => {
  const available = new Set<RoomStyleValue>(['default', ...props.themes])
  if (props.modelValue !== 'default') available.add(props.modelValue)
  return ROOM_STYLES.filter((style) => available.has(style.value))
})

const tierLocked = computed(() => props.tier < 3)
const hint = computed(() => {
  if (tierLocked.value) return 'Themes unlock at tier 3'
  if (props.themes.length === 0) return 'Craft themes at the Theme workshop'
  return null
})
</script>

<template>
  <label class="theme-picker" :title="hint ?? undefined">
    <span class="theme-picker-label">
      <Icon icon="mdi:palette-outline" class="h-4 w-4" />
      Theme
    </span>
    <Select
      :model-value="modelValue"
      :disabled="disabled || tierLocked"
      @update:model-value="emit('update:modelValue', $event as RoomStyleValue)"
    >
      <SelectTrigger class="w-36" size="sm" aria-label="Room theme">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem v-for="style in options" :key="style.value" :value="style.value">
          {{ style.label }}
        </SelectItem>
      </SelectContent>
    </Select>
    <span v-if="hint" class="theme-hint">{{ hint }}</span>
  </label>
</template>

<style scoped>
.theme-picker {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.theme-picker-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--color-theme-primary);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.75;
  white-space: nowrap;
}

.theme-hint {
  color: color-mix(in srgb, var(--color-theme-primary) 55%, transparent);
  font-size: 0.65rem;
  white-space: nowrap;
}
</style>
