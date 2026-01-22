import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerEquipment from '@/modules/dwellers/components/DwellerEquipment.vue'
import { useEquipmentStore } from '@/stores/equipment'
import { useAuthStore } from '@/modules/auth/stores/auth'

vi.mock('@/stores/equipment')
vi.mock('@/modules/auth/stores/auth')

describe('DwellerEquipment', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mockDweller = {
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
    outfit: null
  }

  it('renders equipment slots', () => {
    const wrapper = mount(DwellerEquipment, {
      props: { dweller: mockDweller },
      global: {
        stubs: {
          Icon: true,
          WeaponCard: true,
          OutfitCard: true,
          Teleport: true
        }
      }
    })

    expect(wrapper.text()).toContain('Weapon')
    expect(wrapper.text()).toContain('Outfit')
  })

  it('shows empty slots when no equipment', () => {
    const wrapper = mount(DwellerEquipment, {
      props: { dweller: mockDweller },
      global: {
        stubs: {
          Icon: true,
          WeaponCard: true,
          OutfitCard: true,
          Teleport: true
        }
      }
    })

    expect(wrapper.text()).toContain('Click to equip weapon')
    expect(wrapper.text()).toContain('Click to equip outfit')
  })

  it('emits refresh event', () => {
    const wrapper = mount(DwellerEquipment, {
      props: { dweller: mockDweller },
      global: {
        stubs: {
          Icon: true,
          WeaponCard: true,
          OutfitCard: true,
          Teleport: true
        }
      }
    })

    wrapper.vm.$emit('refresh')
    expect(wrapper.emitted('refresh')).toBeTruthy()
  })
})
