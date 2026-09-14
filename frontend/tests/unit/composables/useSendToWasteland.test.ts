import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const toastMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => toastMocks,
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
  is_adult: true,
  age_group: 'adult',
}

const childDweller = {
  id: 'dweller-child',
  first_name: 'Kid',
  last_name: 'Dweller',
  room_id: null,
  status: 'idle',
  is_adult: false,
  age_group: 'child',
}

describe('useSendToWasteland', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
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
    expect(dispatchSpy).toHaveBeenCalledWith('vault-1', 'dweller-adult', 8, 'test-token', 0, 0)
    expect(sendWasteland.showModal.value).toBe(false)
    expect(sendWasteland.pendingDweller.value).toBeNull()
  })
})
