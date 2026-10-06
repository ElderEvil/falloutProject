import { describe, expect, it } from 'vitest'
import { nextTick, ref } from 'vue'
import { usePartySelection } from '@/modules/progression/composables/usePartySelection'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

const dweller = (id: string, level = 1): DwellerShort =>
  ({
    id,
    first_name: id,
    last_name: 'Dweller',
    level,
    status: 'idle',
  }) as DwellerShort

const makeSelection = (
  overrides: Partial<{
    dwellers: DwellerShort[]
    maxPartySize: number
    maxStimpaks: number
    maxRadaways: number
  }> = {}
) => {
  const dwellers = ref<DwellerShort[]>(overrides.dwellers ?? [])
  const maxPartySize = ref(overrides.maxPartySize ?? 3)
  const maxStimpaks = ref(overrides.maxStimpaks ?? 0)
  const maxRadaways = ref(overrides.maxRadaways ?? 0)
  return {
    selection: usePartySelection({
      dwellers,
      maxPartySize,
      maxStimpaks,
      maxRadaways,
    }),
    maxStimpaks,
    maxRadaways,
    maxPartySize,
    dwellers,
  }
}

describe('usePartySelection', () => {
  it('adds dwellers up to maxPartySize and then rejects extras', () => {
    const { selection } = makeSelection({ maxPartySize: 2 })

    selection.toggleDweller('a')
    selection.toggleDweller('b')
    selection.toggleDweller('c')

    expect(selection.selectedDwellerIds.value).toEqual(['a', 'b'])
  })

  it('removes an already-selected dweller and tracks isSelected / canSubmit', () => {
    const { selection } = makeSelection()
    expect(selection.isSelected('a')).toBe(false)
    expect(selection.canSubmit.value).toBe(false)

    selection.toggleDweller('a')
    expect(selection.isSelected('a')).toBe(true)
    expect(selection.canSubmit.value).toBe(true)

    selection.toggleDweller('a')
    expect(selection.selectedDwellerIds.value).toEqual([])
    expect(selection.canSubmit.value).toBe(false)
  })

  it('resets selection to the opening party and clears supplies', () => {
    const { selection } = makeSelection({ maxStimpaks: 5, maxRadaways: 5 })

    selection.toggleDweller('x')
    selection.setStimpaks([3])
    selection.setRadaways([2])

    selection.resetOnOpen(['a', 'b'])

    expect(selection.selectedDwellerIds.value).toEqual(['a', 'b'])
    expect(selection.selectedStimpaks.value).toBe(0)
    expect(selection.selectedRadaways.value).toBe(0)
  })

  it('clamps supply updates to the min(availability, 15) slider ceiling', () => {
    const { selection } = makeSelection({ maxStimpaks: 20, maxRadaways: 4 })

    expect(selection.stimpakMax.value).toBe(15)
    expect(selection.radawayMax.value).toBe(4)

    selection.setStimpaks([99])
    selection.setRadaways([99])
    expect(selection.selectedStimpaks.value).toBe(15)
    expect(selection.selectedRadaways.value).toBe(4)

    selection.setStimpaks(undefined)
    expect(selection.selectedStimpaks.value).toBe(0)
  })

  it('clamps selected supplies when availability shrinks while open', async () => {
    const { selection, maxStimpaks, maxRadaways } = makeSelection({
      maxStimpaks: 5,
      maxRadaways: 5,
    })

    selection.setStimpaks([4])
    selection.setRadaways([4])

    maxStimpaks.value = 2
    maxRadaways.value = 1
    await nextTick()

    expect(selection.selectedStimpaks.value).toBe(2)
    expect(selection.selectedRadaways.value).toBe(1)
  })

  it('exposes clampToAvailability for an explicit clamp', () => {
    const { selection, maxStimpaks } = makeSelection({ maxStimpaks: 5 })
    selection.setStimpaks([4])
    maxStimpaks.value = 1

    selection.clampToAvailability()

    expect(selection.selectedStimpaks.value).toBe(1)
  })

  it('resolves selected ids against the dwellers argument and builds the payload', () => {
    const { selection } = makeSelection({
      dwellers: [dweller('a'), dweller('b')],
      maxStimpaks: 5,
    })

    selection.toggleDweller('a')
    selection.toggleDweller('missing')
    selection.setStimpaks([2])

    expect(selection.selectedDwellers.value.map((d) => d.id)).toEqual(['a'])
    expect(selection.suppliesPayload()).toEqual({ stimpaks: 2, radaways: 0 })
  })
})
