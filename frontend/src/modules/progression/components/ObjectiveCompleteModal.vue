<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/core/components/ui/dialog'
import RewardCard from '@/core/components/common/RewardCard.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import type { Objective } from '../models/objective'

interface Props {
  objective: Objective | null
  show: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  close: []
  confirm: []
}>()
</script>

<template>
  <Dialog :open="show && !!objective" @update:open="(open) => { if (!open) emit('close') }">
    <DialogContent
      class="flex max-h-[65vh] w-full max-w-md flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-md"
    >
      <DialogHeader
        class="flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
      >
        <Icon icon="mdi:trophy" class="h-8 w-8 text-theme-primary terminal-glow" />
        <DialogTitle class="text-2xl font-bold text-theme-primary terminal-glow">Objective Complete!</DialogTitle>
      </DialogHeader>

      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">

    <div v-if="objective" class="mb-6 flex items-center gap-3 rounded-md border border-theme-primary/30 bg-theme-primary/10 p-4 text-lg text-theme-primary">
      <Icon icon="mdi:flag-checkered" class="h-6 w-6 shrink-0 text-theme-accent" />
      {{ objective.challenge }}
    </div>

    <div v-if="objective" class="grid grid-cols-1 gap-4">
      <RewardCard
        icon="mdi:gift"
        label="Reward"
        :value="objective.reward"
      />
    </div>

      </div>

      <DialogFooter
        class="flex-shrink-0 justify-end border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5"
      >
        <TerminalModalActions
          cancel-label="Close"
          confirm-label="Continue"
          confirm-icon="mdi:check-bold"
          alignment="between"
          @cancel="emit('close')"
          @confirm="emit('confirm')"
        />
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
