import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const toastMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
}))

const apiMocks = vi.hoisted(() => ({
  suggestHeading: vi.fn(),
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => toastMocks,
}))

vi.mock('@/modules/exploration/api/exploration', () => ({
  explorationApi: {
    suggestHeading: apiMocks.suggestHeading,
    dispatchToLocation: vi.fn(),
  },
}))

import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useSendToWasteland } from '@/modules/exploration/composables/useSendToWasteland'

const adultDweller = {
  id: 'dweller-adult',
  first_name: 'Adult',
  last_name: 'Dweller',
  room_id: null,
  status: 'idle',
  age_group: 'adult',
}

const childDweller = {
  id: 'dweller-child',
  first_name: 'Kid',
  last_name: 'Dweller',
  room_id: null,
  status: 'idle',
  age_group: 'child',
}

describe('useSendToWasteland', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    apiMocks.suggestHeading.mockResolvedValue(null)
    useAuthStore().token = 'test-token'
    useDwellerStore().filter.dwellers = [adultDweller, childDweller] as never
  })

  it('refuses to open the duration modal for a dweller too young for the wasteland', () => {
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-child', firstName: 'Kid' })

    expect(toastMocks.error).toHaveBeenCalledWith('Kid is too young for the wasteland')
    expect(sendWasteland.showModal.value).toBe(false)
    expect(sendWasteland.pendingDweller.value).toBeNull()
  })

  it('opens the duration modal for an adult dweller', () => {
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })

    expect(toastMocks.error).not.toHaveBeenCalled()
    expect(sendWasteland.showModal.value).toBe(true)
    expect(sendWasteland.pendingDweller.value?.dwellerId).toBe('dweller-adult')
  })

  it('trusts a known dweller lookup over the store list', () => {
    useDwellerStore().filter.dwellers = []
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open(
      { dwellerId: 'dweller-known', firstName: 'Known' },
      { ...adultDweller, id: 'dweller-known' } as never
    )

    expect(sendWasteland.showModal.value).toBe(true)
  })

  it('dispatches the confirmed exploration and closes the modal', async () => {
    const dispatchSpy = vi
      .spyOn(useExplorationStore(), 'sendDwellerToWasteland')
      .mockResolvedValue({} as never)
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })
    const dispatched = await sendWasteland.confirm({ duration: 8, stimpaks: 0, radaways: 0 })

    expect(dispatched).toBe(true)
    expect(dispatchSpy).toHaveBeenCalledWith(
      'vault-1',
      'dweller-adult',
      8,
      'test-token',
      0,
      0,
      undefined
    )
    expect(sendWasteland.showModal.value).toBe(false)
    expect(sendWasteland.pendingDweller.value).toBeNull()
  })

  it('passes a heading through to the store action when one is chosen', async () => {
    const dispatchSpy = vi
      .spyOn(useExplorationStore(), 'sendDwellerToWasteland')
      .mockResolvedValue({} as never)
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult', headingDegrees: 90 })
    expect(sendWasteland.headingDegrees.value).toBe(90)

    await sendWasteland.confirm({ duration: 8, stimpaks: 0, radaways: 0 })

    expect(dispatchSpy).toHaveBeenCalledWith(
      'vault-1',
      'dweller-adult',
      8,
      'test-token',
      0,
      0,
      90
    )
  })

  it('suggests a heading for a non-map open and sends it on confirm', async () => {
    apiMocks.suggestHeading.mockResolvedValue(135)
    const dispatchSpy = vi
      .spyOn(useExplorationStore(), 'sendDwellerToWasteland')
      .mockResolvedValue({} as never)
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })
    await flushPromises()

    expect(apiMocks.suggestHeading).toHaveBeenCalledTimes(1)
    expect(apiMocks.suggestHeading).toHaveBeenCalledWith('test-token', 'vault-1', expect.any(String), 4)
    expect(sendWasteland.headingDegrees.value).toBe(135)

    await sendWasteland.confirm({ duration: 8, stimpaks: 0, radaways: 0 })

    expect(dispatchSpy).toHaveBeenCalledWith('vault-1', 'dweller-adult', 8, 'test-token', 0, 0, 135)
  })

  it('re-rolls the suggested heading', async () => {
    apiMocks.suggestHeading.mockResolvedValueOnce(10).mockResolvedValueOnce(200)
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })
    await flushPromises()
    expect(sendWasteland.headingDegrees.value).toBe(10)

    sendWasteland.reroll()
    await flushPromises()
    expect(sendWasteland.headingDegrees.value).toBe(200)
  })

  it('re-requests the heading for the duration passed to reroll', async () => {
    apiMocks.suggestHeading.mockResolvedValue(90)
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })
    await flushPromises()

    sendWasteland.reroll(24)
    await flushPromises()

    expect(apiMocks.suggestHeading).toHaveBeenLastCalledWith(
      'test-token',
      'vault-1',
      expect.any(String),
      24
    )
  })

  it('ignores a suggestion that resolves after the modal is cancelled', async () => {
    let resolvePending: (value: number | null) => void = () => {}
    apiMocks.suggestHeading.mockReturnValueOnce(
      new Promise<number | null>((resolve) => {
        resolvePending = resolve
      })
    )
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })
    sendWasteland.cancel()

    resolvePending(42)
    await flushPromises()

    expect(sendWasteland.headingDegrees.value).toBeNull()
    expect(sendWasteland.isSuggestingHeading.value).toBe(false)
  })

  it('ignores a stale suggestion that resolves after a newer modal opening', async () => {
    let resolveStale: (value: number | null) => void = () => {}
    apiMocks.suggestHeading
      .mockReturnValueOnce(
        new Promise<number | null>((resolve) => {
          resolveStale = resolve
        })
      )
      .mockResolvedValueOnce(777)
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })
    sendWasteland.cancel()
    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })
    await flushPromises()
    expect(sendWasteland.headingDegrees.value).toBe(777)

    resolveStale(111)
    await flushPromises()

    expect(sendWasteland.headingDegrees.value).toBe(777)
  })

  it('sends no heading when the suggestion is unavailable', async () => {
    apiMocks.suggestHeading.mockResolvedValue(null)
    const dispatchSpy = vi
      .spyOn(useExplorationStore(), 'sendDwellerToWasteland')
      .mockResolvedValue({} as never)
    const sendWasteland = useSendToWasteland(() => 'vault-1')

    sendWasteland.open({ dwellerId: 'dweller-adult', firstName: 'Adult' })
    await flushPromises()
    expect(sendWasteland.headingDegrees.value).toBeNull()

    await sendWasteland.confirm({ duration: 8, stimpaks: 0, radaways: 0 })

    expect(dispatchSpy).toHaveBeenCalledWith(
      'vault-1',
      'dweller-adult',
      8,
      'test-token',
      0,
      0,
      undefined
    )
  })
})
