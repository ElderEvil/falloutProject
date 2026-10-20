<script setup lang="ts">
import { Icon } from '@iconify/vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import { ROOM_STYLES, type RoomStyleValue } from '../models/room'

defineProps<{
  modelValue: RoomStyleValue
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: RoomStyleValue]
}>()
</script>

<template>
  <label class="theme-picker">
    <span class="theme-picker-label">
      <Icon icon="mdi:palette-outline" class="h-4 w-4" />
      Theme
    </span>
    <Select
      :model-value="modelValue"
      :disabled="disabled"
      @update:model-value="emit('update:modelValue', $event as RoomStyleValue)"
    >
      <SelectTrigger class="w-36" size="sm" aria-label="Room theme">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem v-for="style in ROOM_STYLES" :key="style.value" :value="style.value">
          {{ style.label }}
        </SelectItem>
      </SelectContent>
    </Select>
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
</style>
