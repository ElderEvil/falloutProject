<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Label } from '@/core/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import { formatIdentityLabel } from '@/modules/dwellers/models/dweller'

interface Props {
  id: string
  label: string
  icon: string
  options: readonly string[]
  modelValue?: string
  /** Spans both grid columns (pose, background). */
  full?: boolean
}

defineProps<Props>()

defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const labelClass = 'flex items-center gap-1 text-sm font-medium text-theme-primary/70'
const labelIconClass = 'h-3.5 w-3.5 text-theme-primary/60'

const selectOptions = (values: readonly string[]) =>
  values.map((value) => ({ value, label: formatIdentityLabel(value) }))
</script>

<template>
  <div class="form-field" :class="{ 'form-field-full': full }">
    <Label :for="id" :class="labelClass">
      <Icon :icon="icon" :class="labelIconClass" />
      {{ label }}
    </Label>
    <Select :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
      <SelectTrigger :id="id" class="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem
          v-for="option in selectOptions(options)"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </SelectItem>
      </SelectContent>
    </Select>
  </div>
</template>
