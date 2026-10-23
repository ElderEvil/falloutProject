import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createToastMock } from '../helpers/mocks'
import { createPinia, setActivePinia } from 'pinia'
import * as equipmentService from '@/modules/combat/services/equipment'
import { useEquipmentStore } from '@/modules/combat/stores/equipment'

vi.mock('@/modules/combat/services/equipment')

const toastMock = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => toastMock,
}))

function backendError(detail: string) {
  return { response: { status: 400, data: { detail } } }
}

async function expectSingleErrorToast(
  trigger: () => Promise<unknown>,
  message: string
): Promise<void> {
  const result = await trigger()

  expect(result).toBeNull()
  expect(toastMock.error).toHaveBeenCalledTimes(1)
  expect(toastMock.error).toHaveBeenCalledWith(message)
  expect(toastMock.success).not.toHaveBeenCalled()
}

describe('equipment store error feedback', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('emits one toast with the backend detail when equipping a weapon fails', async () => {
    const store = useEquipmentStore()
    vi.mocked(equipmentService.equipWeapon).mockRejectedValueOnce(backendError('Weapon is broken'))

    await expectSingleErrorToast(
      () => store.equipWeapon('d1', 'w1', 'token'),
      'Failed to equip weapon: Weapon is broken'
    )
  })

  it('emits one toast with the backend detail when unequipping a weapon fails', async () => {
    const store = useEquipmentStore()
    vi.mocked(equipmentService.unequipWeapon).mockRejectedValueOnce(backendError('Weapon is locked'))

    await expectSingleErrorToast(
      () => store.unequipWeapon('d1', 'w1', 'token'),
      'Failed to unequip weapon: Weapon is locked'
    )
  })

  it('emits one toast with the backend detail when equipping an outfit fails', async () => {
    const store = useEquipmentStore()
    vi.mocked(equipmentService.equipOutfit).mockRejectedValueOnce(backendError('Outfit is torn'))

    await expectSingleErrorToast(
      () => store.equipOutfit('d1', 'o1', 'token'),
      'Failed to equip outfit: Outfit is torn'
    )
  })

  it('emits one toast with the backend detail when unequipping an outfit fails', async () => {
    const store = useEquipmentStore()
    vi.mocked(equipmentService.unequipOutfit).mockRejectedValueOnce(backendError('Outfit is locked'))

    await expectSingleErrorToast(
      () => store.unequipOutfit('d1', 'o1', 'token'),
      'Failed to unequip outfit: Outfit is locked'
    )
  })
})
