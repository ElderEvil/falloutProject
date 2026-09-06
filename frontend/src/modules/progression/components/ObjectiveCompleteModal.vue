<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { UModal } from '@/core/components/ui'
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
  <UModal
    :model-value="show && !!objective"
    title="Objective Complete!"
    size="md"
    @close="emit('close')"
  >
    <template #header="{ titleId }">
      <div class="flex items-center gap-3">
        <Icon icon="mdi:trophy" class="h-8 w-8 text-theme-primary terminal-glow" />
        <h2 :id="titleId" class="text-2xl font-bold text-theme-primary terminal-glow">Objective Complete!</h2>
      </div>
    </template>

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

    <template #footer>
      <TerminalModalActions
        cancel-label="Close"
        confirm-label="Continue"
        confirm-icon="mdi:check-bold"
        alignment="between"
        @cancel="emit('close')"
        @confirm="emit('confirm')"
      />
    </template>
  </UModal>
</template>
