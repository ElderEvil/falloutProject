<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { computed } from 'vue'

const props = defineProps<{
  buildModeActive: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleBuildMode'): void
}>()

const iconName = computed(() => (props.buildModeActive ? 'mdi:close' : 'mdi:hammer'))
</script>

<template>
  <TooltipProvider :delay-duration="200">
    <Tooltip>
      <TooltipTrigger as-child>
        <Button
          :variant="buildModeActive ? 'destructive' : 'secondary'"
          size="lg"
          class="h-14 gap-3 border-2 px-6 text-base font-bold uppercase tracking-wide"
          :class="
            buildModeActive
              ? 'border-danger bg-surface-warm'
              : 'border-theme-primary bg-surface-warm text-theme-primary shadow-glow-md hover:shadow-glow-lg'
          "
          @click="emit('toggleBuildMode')"
        >
          <Icon :icon="iconName" class="size-6" />
          <span class="inline-flex items-center gap-2">
            {{ buildModeActive ? 'Cancel Building' : 'Build' }}
            <span
              class="text-xs px-1.5 py-0.5 bg-black/30 border border-current rounded-sm font-bold font-mono opacity-80"
            >
              {{ buildModeActive ? 'ESC' : 'B' }}
            </span>
          </span>
        </Button>
      </TooltipTrigger>
      <TooltipContent>{{ buildModeActive ? 'Cancel Building (Esc)' : 'Build (B)' }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
