<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import { useTrainingStore } from '@/modules/progression/stores/training'
import type { components } from '@/core/types/api.generated'

type DwellerDetailRead = components['schemas']['DwellerReadFull']

interface Props {
  dweller: DwellerDetailRead
  loading?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'chat'): void
  (e: 'assign'): void
  (e: 'recall'): void
  (e: 'train'): void
  (e: 'assign-pet'): void
  (e: 'use-stimpack'): void
  (e: 'use-radaway'): void
  (e: 'unassign'): void
}>()

const trainingStore = useTrainingStore()

const canUseStimpack = computed(() => {
  return (props.dweller.stimpack || 0) > 0 && props.dweller.health < props.dweller.max_health
})

const canUseRadaway = computed(() => {
  return (props.dweller.radaway || 0) > 0 && (props.dweller.radiation || 0) > 0
})

const isTraining = computed(() => {
  return trainingStore.isDwellerTraining(props.dweller.id)
})
</script>

<template>
  <div class="actions-container">
    <UButton variant="primary" size="md" block @click="emit('chat')">
      <Icon icon="mdi:message-text" class="h-5 w-5 mr-2" />
      Chat
    </UButton>

    <div class="room-actions">
      <UButton
        variant="secondary"
        size="md"
        @click="emit('assign')"
        :disabled="loading || dweller.room !== null"
      >
        <Icon icon="mdi:office-building" class="h-5 w-5 mr-2" />
        Assign to Room
      </UButton>

      <UButton
        variant="secondary"
        size="md"
        @click="emit('unassign')"
        :disabled="loading || dweller.room === null"
      >
        <Icon icon="mdi:close-circle" class="h-5 w-5 mr-2" />
        Unassign from Room
      </UButton>
    </div>

    <UButton
      v-if="dweller.status === 'exploring'"
      variant="secondary"
      size="md"
      block
      @click="emit('recall')"
      :disabled="loading"
    >
      <Icon icon="mdi:arrow-u-left-top" class="h-5 w-5 mr-2" />
      Recall from Wasteland
    </UButton>

    <div class="item-actions">
      <UButton
        variant="secondary"
        size="md"
        @click="emit('use-stimpack')"
        :disabled="!canUseStimpack || loading"
        class="item-button"
      >
        <Icon icon="mdi:medical-bag" class="h-5 w-5 mr-2 text-green-500" />
        Use Stimpack
      </UButton>

      <UButton
        variant="secondary"
        size="md"
        @click="emit('use-radaway')"
        :disabled="!canUseRadaway || loading"
        class="item-button"
      >
        <Icon icon="mdi:radiation" class="h-5 w-5 mr-2 text-yellow-500" />
        Use RadAway
      </UButton>
    </div>

    <div class="coming-soon-section">
      <UTooltip text="Train SPECIAL stats to improve dweller abilities">
        <UButton
          variant="secondary"
          size="md"
          block
          @click="emit('train')"
          :disabled="loading || isTraining"
        >
          <Icon icon="mdi:school" class="h-5 w-5 mr-2" />
          {{ isTraining ? 'Training In Progress' : 'Train Stats' }}
        </UButton>
      </UTooltip>

      <UTooltip text="Assign a pet companion - Coming in Phase 3 (Mar-Apr 2026)">
        <UButton variant="secondary" size="md" block disabled class="locked-action-button">
          <Icon icon="mdi:paw" class="h-5 w-5 mr-2" />
          Assign Pet
          <Icon icon="mdi:lock" class="h-4 w-4 ml-auto opacity-50" />
        </UButton>
      </UTooltip>
    </div>
  </div>
</template>

<style scoped>
.actions-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.room-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.item-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.item-button {
  font-size: 0.875rem;
}

.coming-soon-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-theme-glow);
}


</style>
