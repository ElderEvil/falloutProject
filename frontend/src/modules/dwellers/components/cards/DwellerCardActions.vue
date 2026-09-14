<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { isMature } from '../../models/dweller'
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
  (e: 'unassign'): void
  (e: 'send-wasteland'): void
}>()

const trainingStore = useTrainingStore()

const isTraining = computed(() => {
  return trainingStore.isDwellerTraining(props.dweller.id)
})

const isMatureDweller = computed(() => isMature(props.dweller))
const isExploring = computed(() => props.dweller.status === 'exploring')
const exploreTooltip = computed(() =>
  isMatureDweller.value
    ? 'Send this dweller into the wasteland to scavenge for loot'
    : 'Children and teens cannot be sent on exploration'
)
</script>

<template>
  <div class="actions-container">
    <UButton variant="primary" size="md" block @click="emit('chat')">
      <Icon icon="mdi:message-text" class="h-5 w-5 mr-2" />
      Chat
    </UButton>

    <UButton
      v-if="dweller.room === null"
      variant="secondary"
      size="md"
      block
      :title="isMatureDweller ? 'Assign to the best matching room' : 'Assign as an apprentice in a production room'"
      @click="emit('assign')"
      :disabled="loading"
    >
      <Icon
        :icon="isMatureDweller ? 'mdi:office-building' : 'mdi:school-outline'"
        class="h-5 w-5 mr-2"
      />
      {{ isMatureDweller ? 'Assign' : 'Apprentice' }}
    </UButton>

    <UButton
      v-else
      variant="secondary"
      size="md"
      block
      title="Unassign from the current room"
      @click="emit('unassign')"
      :disabled="loading"
    >
      <Icon icon="mdi:close-circle" class="h-5 w-5 mr-2" />
      Unassign
    </UButton>

    <UTooltip :text="exploreTooltip">
      <UButton
        v-if="!isExploring && !dweller.is_dead"
        variant="secondary"
        size="md"
        block
        title="Send to the wasteland"
        @click="emit('send-wasteland')"
        :disabled="loading || !isMatureDweller"
      >
        <Icon icon="mdi:map-marker-radius" class="h-5 w-5 mr-2" />
        Wasteland
      </UButton>
    </UTooltip>

    <UButton
      v-if="isExploring"
      variant="secondary"
      size="md"
      block
      title="Recall from the wasteland"
      @click="emit('recall')"
      :disabled="loading"
    >
      <Icon icon="mdi:arrow-u-left-top" class="h-5 w-5 mr-2" />
      Recall
    </UButton>

    <UTooltip text="Train SPECIAL stats to improve dweller abilities">
      <UButton
        variant="secondary"
        size="md"
        block
        @click="emit('train')"
        :disabled="loading || isTraining"
      >
        <Icon icon="mdi:school" class="h-5 w-5 mr-2" />
        {{ isTraining ? 'Training…' : 'Train' }}
      </UButton>
    </UTooltip>
  </div>
</template>

<style scoped>
.actions-container {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  margin-top: 0.5rem;
}

/* Chat is the primary action, so it keeps a full-width row of its own. */
.actions-container > :first-child {
  grid-column: 1 / -1;
}
</style>
