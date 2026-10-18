<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import RewardItemCard from '@/core/components/common/RewardItemCard.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import type { Objective } from '../models/objective'
import { objectiveRewardDetails } from '../models/objective'

interface Props {
  objective: Objective | null
  show: boolean
}

const props = defineProps<Props>()
const router = useRouter()
const reward = computed(() => objectiveRewardDetails(props.objective?.reward ?? ''))
const newDwellerName = computed(() => {
  return reward.value.kind === 'dweller' ? reward.value.name : ''
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
      <div
        v-if="objective"
        class="mb-6 flex items-center gap-3 rounded-md border border-theme-primary/30 bg-theme-primary/10 p-4 text-lg text-theme-primary"
      >
        <Icon icon="mdi:flag-checkered" class="h-6 w-6 shrink-0 text-theme-accent" />
        {{ objective.challenge }}
      </div>

      <div
        v-if="objective"
        class="grid grid-cols-1 gap-4 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2"
        aria-live="polite"
      >
        <RewardItemCard
          v-if="newDwellerName"
          :name="newDwellerName"
          label="New Dweller"
          meta="Has joined your vault"
          kind="dweller"
          layout="row"
        >
          <template #media>
            <DwellerPortrait
              :alt="newDwellerName"
              image-class="h-32 w-full object-cover object-top sm:h-36"
              fallback-class="size-14 text-theme-primary/50"
            />
          </template>
        </RewardItemCard>

        <RewardItemCard
          v-else
          :kind="reward.kind"
          :name="reward.name"
          :item-type="reward.kind === 'item' ? reward.itemType : undefined"
          :rarity="reward.kind === 'item' ? reward.rarity : undefined"
          :icon="reward.kind === 'currency' ? reward.icon : 'mdi:gift'"
          label="Reward"
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
