<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import RewardCard from '@/core/components/common/RewardCard.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import type { Objective } from '../models/objective'
import { REWARD_TYPE_META } from '../models/quest'

interface Props {
  objective: Objective | null
  show: boolean
}

const props = defineProps<Props>()
const router = useRouter()
const newDwellerName = computed(() => {
  const reward = props.objective?.reward ?? ''
  return reward.toLowerCase().startsWith('dweller:') ? reward.slice('dweller:'.length).trim() : ''
})

const emit = defineEmits<{
  close: []
  confirm: []
}>()

function confirm(): void {
  const vaultId = props.objective?.vault_id
  const showRoster = !!newDwellerName.value && !!vaultId
  emit('confirm')
  if (showRoster) void router.push(`/vault/${vaultId}/dwellers`)
}
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
        :icon="newDwellerName ? REWARD_TYPE_META.dweller.icon : 'mdi:gift'"
        :label="newDwellerName ? REWARD_TYPE_META.dweller.label : 'Reward'"
        :value="newDwellerName || objective.reward"
      />
      <p v-if="newDwellerName" class="text-sm leading-relaxed text-muted-foreground">
        {{ newDwellerName }} has joined your vault. Review their SPECIAL and equipment before
        choosing a job or preparing their first exploration.
      </p>
    </div>

    </div>

    <template #footer>
      <TerminalModalActions
        cancel-label="Close"
        :confirm-label="newDwellerName ? 'View dwellers' : 'Continue'"
        :confirm-icon="newDwellerName ? 'mdi:account-group' : 'mdi:check-bold'"
        alignment="between"
        @cancel="emit('close')"
        @confirm="confirm"
      />
    </template>
  </TerminalModal>
</template>
