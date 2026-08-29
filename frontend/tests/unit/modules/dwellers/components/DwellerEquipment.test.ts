import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import DwellerEquipment from '@/modules/dwellers/components/DwellerEquipment.vue'
import { createMockDwellerDetailContext, mountWithDwellerContext } from '../../../helpers/dwellerDetailContext'
import type { Dweller } from '@/modules/dwellers/models/dweller'
import type { DwellerDetailContext } from '@/modules/dwellers/components/DwellerDetailContext'

vi.mock('@/modules/combat/stores/equipment', () => ({
  useEquipmentStore: () => ({
    fetchWeapons: vi.fn().mockResolvedValue([]),
    fetchOutfits: vi.fn().mockResolvedValue([]),
    getAvailableWeapons: vi.fn().mockReturnValue([]),
    getAvailableOutfits: vi.fn().mockReturnValue([]),
    equipWeapon: vi.fn().mockResolvedValue(undefined),
    equipOutfit: vi.fn().mockResolvedValue(undefined),
    unequipWeapon: vi.fn().mockResolvedValue(undefined),
    unequipOutfit: vi.fn().mockResolvedValue(undefined),
  }),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({
    token: 'test-token',
    isAuthenticated: true,
  }),
}))

function makeDweller(overrides: Partial<Dweller> = {}): Dweller {
  return {
    id: 'dweller-1',
    first_name: 'John',
    last_name: 'Doe',
    S: 5,
    P: 5,
    E: 5,
    C: 5,
    I: 5,
    A: 5,
    L: 5,
    health: 100,
    max_health: 100,
    level: 1,
    experience: 0,
    happiness: 75,
    gender: 'male',
    status: 'idle',
    weapon: null,
    outfit: null,
    ...overrides,
  } as unknown as Dweller
}

function mountEquip(dweller: Dweller, override: Partial<DwellerDetailContext> = {}): VueWrapper {
  const ctx = createMockDwellerDetailContext({
    dweller: ref(dweller) as never,
    vaultId: ref('v1') as never,
    ...override,
  })
  const wrapper = mountWithDwellerContext(DwellerEquipment, {
    context: ctx,
    global: {
      stubs: {
        Icon: true,
        Teleport: true,
        EquipmentCard: {
          template: '<button class="equip-slot" @click="$emit(\'unequip\')"></button>',
          props: ['item', 'type', 'equipped', 'showActions'],
        },
      },
    },
  })
  return wrapper
}

describe('DwellerEquipment', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders equipment slots', () => {
    const wrapper = mountEquip(makeDweller())
    expect(wrapper.text()).toContain('Weapon')
    expect(wrapper.text()).toContain('Outfit')
  })

  it('shows empty slots when no equipment', () => {
    const wrapper = mountEquip(makeDweller())
    expect(wrapper.text()).toContain('Click to equip weapon')
    expect(wrapper.text()).toContain('Click to equip outfit')
  })

  it('calls the refresh action when a weapon is unequipped', async () => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref(makeDweller({ weapon: { id: 'w1' } })) as never,
      vaultId: ref('v1') as never,
    })
    const wrapper = mountWithDwellerContext(DwellerEquipment, {
      context: ctx,
      global: {
        stubs: {
          Icon: true,
          Teleport: true,
          EquipmentCard: {
            template: '<button class="equip-slot" @click="$emit(\'unequip\')"></button>',
            props: ['item', 'type', 'equipped', 'showActions'],
          },
        },
      },
    })

    await flushPromises()
    await wrapper.find('.equip-slot').trigger('click')
    await flushPromises()

    expect(ctx.actions.refresh).toHaveBeenCalledOnce()
  })
})
