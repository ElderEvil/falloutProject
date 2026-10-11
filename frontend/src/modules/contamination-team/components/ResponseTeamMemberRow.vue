<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import type { HazardTeamMemberRead } from '../models/contaminationTeam'

defineProps<{ member: HazardTeamMemberRead; active: boolean; disabled: boolean }>()
defineEmits<{
  'view-dweller': [dwellerId: string]
  'set-place': [active: boolean]
}>()
</script>

<template>
  <li
    class="flex items-center justify-between gap-2 rounded border-l-[3px] border-theme-primary/50 bg-terminal-background px-2.5 py-1.5"
  >
    <Button
      variant="link"
      class="h-auto min-w-0 justify-start whitespace-normal p-0 text-left text-sm"
      @click="$emit('view-dweller', member.dweller_id)"
    >
      <span class="break-words">{{ member.name || 'Unknown dweller' }}</span>
      <Icon icon="mdi:open-in-new" class="size-3 shrink-0" />
    </Button>
    <span class="flex shrink-0 items-center gap-2 text-xs">
      <span class="text-theme-primary/70">LVL {{ member.level }}</span>
      <Button variant="outline" size="xs" :disabled="disabled" @click="$emit('set-place', !active)">
        {{ active ? 'Bench' : 'Activate' }}
      </Button>
    </span>
  </li>
</template>
