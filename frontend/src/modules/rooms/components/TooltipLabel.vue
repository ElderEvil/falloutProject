<script setup lang="ts">
import { Tooltip, TooltipContent, TooltipTrigger } from '@/core/components/ui/tooltip'

defineProps<{ label: string }>()
</script>

<template>
  <Tooltip>
    <TooltipTrigger as-child>
      <slot />
    </TooltipTrigger>
    <TooltipContent>{{ label }}</TooltipContent>
  </Tooltip>
</template>