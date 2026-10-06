import { computed, ref, toValue, watch } from 'vue'
import type { ComputedRef, MaybeRefOrGetter, Ref } from 'vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

/** Supplies slider ceiling; vault stock above this is still shown as the "/ max" total. */
const SUPPLY_SLIDER_CAP = 15

export interface PartySelectionOptions {
  /** Candidate dwellers used to resolve selected ids back into records (ref or getter). */
  dwellers: MaybeRefOrGetter<DwellerShort[]>
  /** Maximum selectable party size (ref or getter). */
  maxPartySize: MaybeRefOrGetter<number>
  /** Stimpaks available in the vault (ref or getter). Slider max is min(this, 15). */
  maxStimpaks: MaybeRefOrGetter<number>
  /** Radaways available in the vault (ref or getter). Slider max is min(this, 15). */
  maxRadaways: MaybeRefOrGetter<number>
}

export interface PartySelection {
  /** Selected dweller ids, in slot order. Mutate through the helpers below. */
  selectedDwellerIds: Ref<string[]>
  /** Stimpaks chosen for the party. */
  selectedStimpaks: Ref<number>
  /** Radaways chosen for the party. */
  selectedRadaways: Ref<number>
  /** Slider ceiling for stimpaks: min(maxStimpaks, 15). */
  stimpakMax: ComputedRef<number>
  /** Slider ceiling for radaways: min(maxRadaways, 15). */
  radawayMax: ComputedRef<number>
  /** Selected ids resolved against the dwellers argument, in slot order. */
  selectedDwellers: ComputedRef<DwellerShort[]>
  /** True once at least one dweller is selected. */
  canSubmit: ComputedRef<boolean>
  isSelected: (dwellerId: string) => boolean
  /** Add/remove a dweller; additions are rejected once maxPartySize is reached. */
  toggleDweller: (dwellerId: string) => void
  setStimpaks: (value: number[] | undefined) => void
  setRadaways: (value: number[] | undefined) => void
  /** Sync selection to the opening party and clear supplies (call when the picker opens). */
  resetOnOpen: (currentPartyIds: string[]) => void
  /** Clamp both supply selections to the availability passed into the composable. */
  clampToAvailability: () => void
  suppliesPayload: () => { stimpaks: number; radaways: number }
}

/**
 * Party picker state shared by the quest and dispatch flows: which dwellers are
 * selected (capped at maxPartySize) and how many stimpaks/radaways they carry.
 *
 * Eligibility fetching is deliberately NOT owned here — the quest flow fetches
 * eligible dwellers and feeds the resulting available list to the caller. This
 * composable only resolves selected ids against `dwellers`.
 *
 * Callers may pass refs or getters for every option; values are read lazily via
 * `toValue`, so reactive props can be forwarded directly.
 */
export function usePartySelection(options: PartySelectionOptions): PartySelection {
  const selectedDwellerIds = ref<string[]>([])
  const selectedStimpaks = ref(0)
  const selectedRadaways = ref(0)

  const stimpakMax = computed(() => Math.min(toValue(options.maxStimpaks), SUPPLY_SLIDER_CAP))
  const radawayMax = computed(() => Math.min(toValue(options.maxRadaways), SUPPLY_SLIDER_CAP))

  const clampToAvailability = () => {
    selectedStimpaks.value = Math.min(selectedStimpaks.value, toValue(options.maxStimpaks))
    selectedRadaways.value = Math.min(selectedRadaways.value, toValue(options.maxRadaways))
  }

  // Supplies shrink while the picker stays open — never carry more than what is available.
  watch(() => [toValue(options.maxStimpaks), toValue(options.maxRadaways)], clampToAvailability)

  const setStimpaks = (value: number[] | undefined) => {
    selectedStimpaks.value = Math.min(value?.[0] ?? 0, stimpakMax.value)
  }

  const setRadaways = (value: number[] | undefined) => {
    selectedRadaways.value = Math.min(value?.[0] ?? 0, radawayMax.value)
  }

  const toggleDweller = (dwellerId: string) => {
    const index = selectedDwellerIds.value.indexOf(dwellerId)
    if (index === -1) {
      // Add dweller if not at max
      if (selectedDwellerIds.value.length < toValue(options.maxPartySize)) {
        selectedDwellerIds.value.push(dwellerId)
      }
    } else {
      // Remove dweller
      selectedDwellerIds.value.splice(index, 1)
    }
  }

  const isSelected = (dwellerId: string) => selectedDwellerIds.value.includes(dwellerId)

  const selectedDwellers = computed(() =>
    selectedDwellerIds.value
      .map((id) => toValue(options.dwellers).find((d) => d.id === id))
      .filter((d): d is DwellerShort => d !== undefined)
  )

  const canSubmit = computed(() => selectedDwellerIds.value.length > 0)

  const resetOnOpen = (currentPartyIds: string[]) => {
    selectedDwellerIds.value = [...currentPartyIds]
    selectedStimpaks.value = 0
    selectedRadaways.value = 0
  }

  const suppliesPayload = () => ({
    stimpaks: selectedStimpaks.value,
    radaways: selectedRadaways.value,
  })

  return {
    selectedDwellerIds,
    selectedStimpaks,
    selectedRadaways,
    stimpakMax,
    radawayMax,
    selectedDwellers,
    canSubmit,
    isSelected,
    toggleDweller,
    setStimpaks,
    setRadaways,
    resetOnOpen,
    clampToAvailability,
    suppliesPayload,
  }
}
