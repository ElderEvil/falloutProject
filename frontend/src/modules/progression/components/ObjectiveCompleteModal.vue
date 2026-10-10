<script setup lang="ts">
import { Icon } from '@iconify/vue'
import RewardCard from '@/core/components/common/RewardCard.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
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
  <TerminalModal
    :open="show && !!objective"
    title="Objective Complete!"
    icon="mdi:trophy"
    size="md"
    max-height="65"
    @close="emit('close')"
  >
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
  </TerminalModal>
</template>
