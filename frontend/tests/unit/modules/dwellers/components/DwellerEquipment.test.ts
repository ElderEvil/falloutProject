import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref, nextTick } from 'vue'
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

const petsStoreMock = vi.hoisted(() => ({
  fetchPets: vi.fn(),
  getAvailablePets: vi.fn(),
  equipPet: vi.fn(),
  unequipPet: vi.fn(),
}))

vi.mock('@/modules/pets/stores/pets', () => ({
  usePetsStore: () => petsStoreMock,
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
    pet: null,
    ...overrides,
  } as unknown as Dweller
}

const sharedStubs = {
  Icon: true,
  Teleport: { template: '<div><slot /></div>' },
  EquipmentCard: {
    template: '<button class="equip-slot" @click="$emit(\'unequip\')"></button>',
    props: ['item', 'type', 'equipped', 'showActions'],
  },
}

const petCardStub = {
  template:
    '<button class="pet-slot" @click="$emit(equipped ? \'unequip\' : \'equip\')"></button>',
  props: ['pet', 'equipped', 'showActions'],
}

function mountEquip(
  dweller: Dweller,
  override: Partial<DwellerDetailContext> = {},
  stubs: Record<string, unknown> = {}
): VueWrapper {
  const ctx = createMockDwellerDetailContext({
    dweller: ref(dweller) as never,
    vaultId: ref('v1') as never,
    ...override,
  })
  const wrapper = mountWithDwellerContext(DwellerEquipment, {
    context: ctx,
    global: {
      stubs: { ...sharedStubs, ...stubs },
    },
  })
  return wrapper
}

describe('DwellerEquipment', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    petsStoreMock.fetchPets.mockResolvedValue([])
    petsStoreMock.getAvailablePets.mockReturnValue([])
    petsStoreMock.equipPet.mockResolvedValue(undefined)
    petsStoreMock.unequipPet.mockResolvedValue(undefined)
  })

  it('renders equipment slots', () => {
    const wrapper = mountEquip(makeDweller())
    expect(wrapper.text()).toContain('Weapon')
    expect(wrapper.text()).toContain('Outfit')
    expect(wrapper.text()).toContain('Pet')
  })

  it('shows empty slots when no equipment', () => {
    const wrapper = mountEquip(makeDweller())
    expect(wrapper.text()).toContain('Click to equip weapon')
    expect(wrapper.text()).toContain('Click to equip outfit')
    expect(wrapper.text()).toContain('Click to equip pet')
  })

  it('opens the shared modal when an empty slot is selected', async () => {
    const wrapper = mountEquip(makeDweller())

    await wrapper.findAll('button.empty-slot')[0].trigger('click')
    await flushPromises()
    await nextTick()
    await flushPromises()

    const modal = wrapper.findComponent({ name: 'Dialog' })
    expect(modal.props('open')).toBe(true)
    expect(wrapper.text()).toContain('Select Weapon')
  })

  it('calls the refresh action when a weapon is unequipped', async () => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref(makeDweller({ weapon: { id: 'w1' } })) as never,
      vaultId: ref('v1') as never,
    })
    const wrapper = mountWithDwellerContext(DwellerEquipment, {
      context: ctx,
      global: {
        stubs: sharedStubs,
      },
    })

    await flushPromises()
    await wrapper.find('.equip-slot').trigger('click')
    await flushPromises()

    expect(ctx.actions.refresh).toHaveBeenCalledOnce()
  })

  it('renders the equipped pet card with its bonus summary', async () => {
    const wrapper = mountEquip(
      makeDweller({
        pet: {
          id: 'pet-1',
          name: 'Dogmeat',
          rarity: 'rare',
          value: 100,
          image_url: null,
          dweller_id: 'dweller-1',
          storage_id: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          effect: {
            strength: 2,
            perception: 0,
            endurance: 0,
            charisma: 0,
            intelligence: 0,
            agility: 0,
            luck: 0,
            max_health: 50,
            damage_pct: 0,
            incident_response_pct: 0,
            radiation_resist_pct: 0,
            happiness: 0,
            caps_pct: 0,
            xp_pct: 0,
            training_speed_pct: 0,
          },
        },
      })
    )
    await flushPromises()

    expect(wrapper.text()).toContain('Dogmeat')
    expect(wrapper.text()).toContain('Strength +2')
    expect(wrapper.text()).toContain('Max HP +50')
  })

  it('equips a pet from the inventory picker with the test pet id', async () => {
    petsStoreMock.getAvailablePets.mockReturnValue([
      {
        id: 'pet-9',
        name: 'CX404',
        rarity: 'legendary',
        value: 500,
        image_url: null,
        dweller_id: null,
        storage_id: 'storage-1',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        effect: {
          strength: 0,
          perception: 0,
          endurance: 0,
          charisma: 0,
          intelligence: 0,
          agility: 0,
          luck: 0,
          max_health: 0,
          damage_pct: 0,
          incident_response_pct: 0,
          radiation_resist_pct: 0,
          happiness: 0,
          caps_pct: 0,
          xp_pct: 0,
          training_speed_pct: 0,
        },
      },
    ])
    const wrapper = mountEquip(makeDweller(), {}, { PetCard: petCardStub })
    await flushPromises()

    await wrapper.findAll('button.empty-slot')[2].trigger('click')
    await flushPromises()
    await nextTick()
    await flushPromises()

    expect(wrapper.text()).toContain('Select Pet')
    await wrapper.find('.pet-slot').trigger('click')
    await flushPromises()

    expect(petsStoreMock.equipPet).toHaveBeenCalledWith('dweller-1', 'pet-9', 'test-token')
    expect(wrapper.findComponent({ name: 'Dialog' }).props('open')).toBe(false)
  })

  it('renders the empty state in the pet picker when no pets are available', async () => {
    const wrapper = mountEquip(makeDweller())
    await flushPromises()

    await wrapper.findAll('button.empty-slot')[2].trigger('click')
    await flushPromises()
    await nextTick()
    await flushPromises()

    expect(wrapper.text()).toContain('No pets available')
  })

  it('unequips the equipped pet through the store', async () => {
    const wrapper = mountWithDwellerContext(DwellerEquipment, {
      context: createMockDwellerDetailContext({
        dweller: ref(
          makeDweller({
            pet: {
              id: 'pet-1',
              name: 'Dogmeat',
              rarity: 'rare',
              value: 100,
              image_url: null,
              dweller_id: 'dweller-1',
              storage_id: null,
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              effect: {
                strength: 0,
                perception: 0,
                endurance: 0,
                charisma: 0,
                intelligence: 0,
                agility: 0,
                luck: 0,
                max_health: 0,
                damage_pct: 0,
                incident_response_pct: 0,
                radiation_resist_pct: 0,
                happiness: 0,
                caps_pct: 0,
                xp_pct: 0,
                training_speed_pct: 0,
              },
            },
          })
        ) as never,
        vaultId: ref('v1') as never,
      }),
      global: {
        stubs: { ...sharedStubs, PetCard: petCardStub },
      },
    })
    await flushPromises()

    await wrapper.find('.pet-slot').trigger('click')
    await flushPromises()

    expect(petsStoreMock.unequipPet).toHaveBeenCalledWith('dweller-1', 'pet-1', 'test-token')
  })
})
