<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Label } from '@/core/components/ui/label'
import { Button } from '@/core/components/ui/button'
import { Slider } from '@/core/components/ui/slider'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import { COMPASS_LABELS, compassLabel } from '@/modules/map/utils/bearing'

const HEADING_STEPS = COMPASS_LABELS.map((_label, index) => index * 45)

interface Props {
  show: boolean
  dwellerName: string
  maxStimpaks: number
  maxRadaways: number
  allowRadaway?: boolean
  /** Formatted compass heading (e.g. "E / 90°") for a heading-bearing run. */
  heading?: string | null
  canReroll?: boolean
  isSuggestingHeading?: boolean
  /** Raw compass degrees for the dial highlight; null when unknown. */
  headingDegrees?: number | null
  /** Optional values to seed the reset-on-open (chat prefill); undefined keeps defaults. */
  initialDuration?: number
  initialStimpaks?: number
  initialRadaways?: number
}

const props = withDefaults(defineProps<Props>(), {
  allowRadaway: true,
  heading: null,
  canReroll: false,
  isSuggestingHeading: false,
  headingDegrees: null,
})

const emit = defineEmits<{
  confirm: [payload: { duration: number; stimpaks: number; radaways: number }]
  cancel: []
  reroll: [duration: number]
  selectHeading: [degrees: number]
}>()

const selectedDuration = ref(4)
const selectedStimpaks = ref(0)
const selectedRadaways = ref(0)
const selectedHeading = ref<number | null>(null)
const dialOpen = ref(false)

const DURATION_DEFAULT = 4
const DEFAULT_STIMPAKS = 5
const DEFAULT_RADAWAYS = 5
const DWELLER_MAX_SUPPLIES = 15

const activeDialLabel = computed(() => {
  const degrees = selectedHeading.value ?? props.headingDegrees
  return degrees === null || degrees === undefined ? null : compassLabel(degrees)
})

watch(
  () => props.show,
  (isVisible, wasVisible) => {
    if (isVisible && !wasVisible) {
      selectedDuration.value = props.initialDuration ?? DURATION_DEFAULT
      selectedStimpaks.value = Math.min(
        props.initialStimpaks ?? DEFAULT_STIMPAKS,
        props.maxStimpaks,
        DWELLER_MAX_SUPPLIES
      )
      selectedRadaways.value = props.allowRadaway
        ? Math.min(props.initialRadaways ?? DEFAULT_RADAWAYS, props.maxRadaways, DWELLER_MAX_SUPPLIES)
        : 0
      selectedHeading.value = null
      dialOpen.value = false
    }
  },
  { immediate: true }
)

const handleConfirm = () => {
  emit('confirm', {
    duration: selectedDuration.value,
    stimpaks: selectedStimpaks.value,
    radaways: props.allowRadaway ? selectedRadaways.value : 0,
  })
}

const selectDuration = (duration: number) => {
  if (duration === selectedDuration.value) return
  selectedDuration.value = duration
  // A manual compass pick wins for this opening: duration changes must not
  // auto-reroll over it. The explicit Change button still re-rolls.
  if (props.canReroll && selectedHeading.value === null) emit('reroll', duration)
}

const selectManualHeading = (degrees: number) => {
  selectedHeading.value = degrees
  emit('selectHeading', degrees)
}

const handleChange = () => {
  selectedHeading.value = null
  emit('reroll', selectedDuration.value)
}

const setStimpaks = (value: number[] | undefined) => {
  selectedStimpaks.value = value?.[0] ?? 0
}
const setRadaways = (value: number[] | undefined) => {
  selectedRadaways.value = value?.[0] ?? 0
}
</script>

<template>
  <TerminalModal
    :open="show"
    title="Select Exploration Duration"
    icon="mdi:clock-outline"
    icon-class="inline h-6 w-6 text-theme-primary"
    size="xl"
    max-height="75"
    header-class="flex flex-shrink-0 flex-row items-center gap-2 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
    @close="emit('cancel')"
  >
      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
        <p class="mb-6 text-sm text-theme-primary/70">How long should {{ dwellerName }} explore?</p>

        <div
          v-if="heading || isSuggestingHeading || canReroll"
          class="mb-6 rounded-lg border border-theme-primary/25 bg-surface-sunken p-4"
        >
          <h4 class="mb-2 flex items-center gap-2 text-base font-bold text-theme-primary">
            <Icon icon="mdi:compass-outline" class="inline h-5 w-5" />
            Travel Heading
          </h4>
          <p v-if="isSuggestingHeading" class="text-sm text-theme-primary/60">
            Choosing a direction…
          </p>
          <template v-else>
            <div class="flex items-center justify-between gap-3">
              <p v-if="heading" class="text-sm text-theme-primary/80">
                {{ heading }} — {{ dwellerName }} travels in this direction.
              </p>
              <p v-else class="text-sm text-theme-primary/60">
                No direction suggested. You can try again.
              </p>
              <Button
                v-if="canReroll"
                variant="outline"
                size="xs"
                type="button"
                class="font-mono text-xs font-bold"
                @click="handleChange"
              >
                Change
              </Button>
            </div>
            <div class="mt-3">
              <Button
                variant="outline"
                size="xs"
                type="button"
                class="heading-dial-toggle font-mono text-xs font-bold"
                @click="dialOpen = !dialOpen"
              >
                <Icon icon="mdi:compass" class="inline h-4 w-4" />
                {{ dialOpen ? 'Hide directions' : 'Pick direction' }}
              </Button>
              <div v-if="dialOpen" class="compass-dial mt-3 grid grid-cols-4 gap-2">
                <Button
                  v-for="(label, index) in COMPASS_LABELS"
                  :key="label"
                  variant="outline"
                  size="xs"
                  type="button"
                  class="dial-direction font-mono text-xs font-bold"
                  :aria-pressed="activeDialLabel === label"
                  :class="
                    activeDialLabel === label
                      ? 'border-theme-primary bg-theme-primary/25 text-theme-primary shadow-glow-md'
                      : ''
                  "
                  @click="selectManualHeading(HEADING_STEPS[index])"
                >
                  {{ label }}
                </Button>
              </div>
            </div>
          </template>
        </div>

        <div class="mb-6 grid grid-cols-3 gap-3">
          <button
            v-for="duration in [1, 2, 4, 8, 12, 24]"
            :key="duration"
            @click="selectDuration(duration)"
            class="duration-button cursor-pointer rounded-md border-2 border-theme-primary/30 bg-theme-primary/10 p-3 font-mono text-base font-bold text-theme-primary transition-all duration-200 hover:border-theme-primary/60 hover:bg-theme-primary/20"
            :class="
              selectedDuration === duration
                ? 'active border-theme-primary bg-theme-primary/25 shadow-glow-md'
                : ''
            "
          >
            {{ duration }}h
          </button>
        </div>

        <div class="mb-8 rounded-lg border border-theme-primary/25 bg-surface-sunken p-4">
          <h4 class="mb-4 flex items-center gap-2 text-base font-bold text-theme-primary">
            <Icon icon="mdi:medical-bag" class="inline h-5 w-5" />
            Medical Supplies
          </h4>
          <div class="flex flex-col gap-5">
            <div class="flex flex-col">
              <div class="flex items-center justify-between mb-1">
                <Label class="text-xs text-theme-primary/80">Stimpaks (Heals HP)</Label>
                <span class="text-xs font-bold text-theme-primary"
                  >{{ selectedStimpaks }} / {{ maxStimpaks }}</span
                >
              </div>
              <Slider
                :model-value="[selectedStimpaks]"
                :min="0"
                :max="Math.max(1, Math.min(maxStimpaks, 15))"
                aria-label="Stimpaks to carry"
                @update:model-value="setStimpaks"
              />
            </div>
            <div v-if="allowRadaway" class="flex flex-col">
              <div class="flex items-center justify-between mb-1">
                <Label class="text-xs text-theme-primary/80">RadAway (Removes Rads)</Label>
                <span class="text-xs font-bold text-theme-primary"
                  >{{ selectedRadaways }} / {{ maxRadaways }}</span
                >
              </div>
              <Slider
                :model-value="[selectedRadaways]"
                :min="0"
                :max="Math.max(1, Math.min(maxRadaways, 15))"
                aria-label="RadAway to carry"
                @update:model-value="setRadaways"
              />
            </div>
            <p v-else class="text-xs leading-relaxed text-theme-primary/80">
              RadAway isn't needed: this dweller is radiation immune.
            </p>
          </div>
          <p class="mt-2 text-[10px] text-theme-primary/55">
            * Selected items will be removed from vault storage and used automatically in the
            wasteland.
          </p>
        </div>
      </div>

    <template #footer>
      <TerminalModalActions
        cancel-label="Cancel"
        confirm-label="Send to Wasteland"
        @cancel="emit('cancel')"
        @confirm="handleConfirm"
      />
    </template>
  </TerminalModal>
</template>
