<script setup lang="ts">
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'

withDefaults(defineProps<{
  id: string
  label: string
  type?: string
  placeholder?: string
  autocomplete?: string
  required?: boolean
}>(), {
  type: 'text',
  required: false,
})

const model = defineModel<string>({ required: true })
</script>

<template>
  <div class="flex flex-col gap-2">
    <Label :for="id" class="text-xs font-bold tracking-[0.08em] text-theme-primary/75">
      > {{ label }}<span v-if="required" class="text-danger" aria-hidden="true">*</span>
    </Label>
    <Input
      :id="id"
      v-model="model"
      :type="type"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :required="required"
      class="h-11 border-theme-primary/40 bg-surface text-theme-primary placeholder:text-theme-primary/35 focus-visible:border-theme-primary"
    />
  </div>
</template>
