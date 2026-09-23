<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
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
const explorationStore = useExplorationStore()

const isTraining = computed(() => trainingStore.isDwellerTraining(props.dweller.id))

const isMatureDweller = computed(() => isMature(props.dweller))
const isExploring = computed(() => props.dweller.status === 'exploring')
const exploration = computed(() => explorationStore.getExplorationByDwellerId(props.dweller.id))
/** Recall only applies while exploring; the dweller stays `exploring` on the return leg. */
const isReturning = computed(() => exploration.value?.status === 'returning')
const canRecall = computed(() => exploration.value?.status === 'active')
/** Away dwellers are out of the vault: room, training and wasteland actions do not apply. */
const isAway = computed(
  () => props.dweller.status === 'exploring' || props.dweller.status === 'questing'
)
const isGone = computed(() => isAway.value || props.dweller.is_dead)
const exploreTooltip = computed(() =>
  isMatureDweller.value
    ? 'Send this dweller into the wasteland to scavenge for loot'
    : 'Children and teens cannot be sent on exploration'
)
</script>

<template>
  <div class="actions-container">
    <Button variant="default" class="w-full" @click="emit('chat')">
      <Icon icon="mdi:message-text" class="h-5 w-5 mr-2" />
      Chat
    </Button>

    <TooltipProvider :delay-duration="200">
      <Tooltip v-if="dweller.room === null && !isGone">
        <TooltipTrigger as-child>
          <Button variant="secondary" class="w-full" @click="emit('assign')" :disabled="loading">
            <Icon
              :icon="isMatureDweller ? 'mdi:office-building' : 'mdi:school-outline'"
              class="h-5 w-5 mr-2"
            />
            {{ isMatureDweller ? 'Assign' : 'Apprentice' }}
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">{{
          isMatureDweller
            ? 'Assign to the best matching room'
            : 'Assign as an apprentice in a production room'
        }}</TooltipContent>
      </Tooltip>

      <Tooltip v-else-if="!isGone">
        <TooltipTrigger as-child>
          <Button variant="secondary" class="w-full" @click="emit('unassign')" :disabled="loading">
            <Icon icon="mdi:close-circle" class="h-5 w-5 mr-2" />
            Unassign
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">Unassign from the current room</TooltipContent>
      </Tooltip>

      <Tooltip v-if="!isGone">
        <TooltipTrigger as-child>
          <Button
            variant="secondary"
            class="w-full"
            @click="emit('send-wasteland')"
            :disabled="loading || !isMatureDweller"
          >
            <Icon icon="mdi:map-marker-radius" class="h-5 w-5 mr-2" />
            Wasteland
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">{{ exploreTooltip }}</TooltipContent>
      </Tooltip>

      <Tooltip v-if="isReturning">
        <TooltipTrigger as-child>
          <Button variant="secondary" class="w-full" disabled>
            <Icon icon="mdi:home-import-outline" class="h-5 w-5 mr-2" />
            Returning
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">Heading home from the wasteland</TooltipContent>
      </Tooltip>

      <Tooltip v-else-if="canRecall">
        <TooltipTrigger as-child>
          <Button variant="secondary" class="w-full" @click="emit('recall')" :disabled="loading">
            <Icon icon="mdi:arrow-u-left-top" class="h-5 w-5 mr-2" />
            Recall
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">Recall from the wasteland</TooltipContent>
      </Tooltip>

      <Tooltip v-if="!isGone">
        <TooltipTrigger as-child>
          <Button
            variant="secondary"
            class="w-full"
            @click="emit('train')"
            :disabled="loading || isTraining"
          >
            <Icon icon="mdi:school" class="h-5 w-5 mr-2" />
            {{ isTraining ? 'Training…' : 'Train' }}
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">Train SPECIAL stats to improve dweller abilities</TooltipContent>
      </Tooltip>
    </TooltipProvider>
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
