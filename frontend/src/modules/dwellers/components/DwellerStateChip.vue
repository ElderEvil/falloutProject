<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'

defineOptions({ inheritAttrs: false })

type ChipSize = 'small' | 'medium' | 'large'

interface Props {
  icon: string
  label?: string
  size?: ChipSize
  title?: string
}

const props = withDefaults(defineProps<Props>(), { label: '', size: 'small', title: undefined })

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'medium':
      return { container: 'h-6 px-2', icon: 'h-4 w-4', text: 'text-sm' }
    case 'large':
      return { container: 'h-7 px-2.5', icon: 'h-5 w-5', text: 'text-base' }
    default:
      return { container: 'h-5 px-1.5', icon: 'h-3 w-3', text: 'text-xs' }
  }
})
</script>

<template>
  <TooltipProvider :delay-duration="200">
    <Tooltip>
      <TooltipTrigger as-child>
        <div
          v-bind="$attrs"
          class="state-chip inline-flex items-center gap-1 rounded border transition-all"
          :class="sizeClasses.container"
        >
          <Icon :icon="icon" :class="sizeClasses.icon" />
          <span v-if="label" :class="[sizeClasses.text, 'font-medium']">{{ label }}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent v-if="title" side="top">{{ title }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
