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

const backendError = (detail: string) => ({ response: { status: 400, data: { detail } } })

type Store = ReturnType<typeof useEquipmentStore>

describe('equipment store error feedback', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it.each([
    [
      'equipping a weapon',
      equipmentService.equipWeapon,
      (store: Store) => store.equipWeapon('d1', 'w1'),
      'Weapon is broken',
      'Failed to equip weapon: Weapon is broken',
    ],
    [
      'unequipping a weapon',
      equipmentService.unequipWeapon,
      (store: Store) => store.unequipWeapon('w1'),
      'Weapon is locked',
      'Failed to unequip weapon: Weapon is locked',
    ],
    [
      'equipping an outfit',
      equipmentService.equipOutfit,
      (store: Store) => store.equipOutfit('d1', 'o1'),
      'Outfit is torn',
      'Failed to equip outfit: Outfit is torn',
    ],
    [
      'unequipping an outfit',
      equipmentService.unequipOutfit,
      (store: Store) => store.unequipOutfit('o1'),
      'Outfit is locked',
      'Failed to unequip outfit: Outfit is locked',
    ],
  ] as [string, () => unknown, (store: Store) => Promise<unknown>, string, string][])(
    'emits one toast with the backend detail when %s fails',
    async (_, service, trigger, detail, message) => {
      const store = useEquipmentStore()
      vi.mocked(service).mockRejectedValueOnce(backendError(detail))

      const result = await trigger(store)

      expect(result).toBeNull()
      expect(toastMock.error).toHaveBeenCalledTimes(1)
      expect(toastMock.error).toHaveBeenCalledWith(message)
      expect(toastMock.success).not.toHaveBeenCalled()
    }
  )
})
