import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createIconifyMock, createRouterMock } from '../helpers/mocks'
import CombatZonePreview from '@/modules/pvp/views/CombatZonePreview.vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

const { getDwellersByVaultMock } = vi.hoisted(() => ({ getDwellersByVaultMock: vi.fn() }))

vi.mock('vue-router', () => createRouterMock())
vi.mock('@iconify/vue', () => createIconifyMock())
vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getDwellersByVault: getDwellersByVaultMock,
  getDweller: vi.fn(),
}))

function dweller(id: string, first: string, last: string, level: number): DwellerShort {
  return {
    id,
    first_name: first,
    last_name: last,
    thumbnail_url: null,
    level,
    health: 100,
    max_health: 100,
    radiation: 0,
    happiness: 80,
    status: 'idle',
    age_group: 'adult',
    gender: 'female',
    rarity: 'common',
    strength: 6,
    perception: 5,
    endurance: 7,
    charisma: 4,
    intelligence: 6,
    agility: 5,
    luck: 3,
    combat_power: 20,
    is_default_portrait: true,
    effective_max_health: 100,
  } as DwellerShort
}

const roster = [
  dweller('d1', 'Marlene', 'Voss', 14),
  dweller('d2', 'Curtis', 'Abernathy', 11),
  dweller('d3', 'Nia', 'Okonkwo', 9),
  dweller('d4', 'Desmond', 'Reyes', 12),
]
const challengers = [dweller('c1', 'Priya', 'Nandakumar', 10), dweller('c2', 'Bram', 'Hollis', 8)]

describe('CombatZonePreview', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getDwellersByVaultMock.mockReset()
    getDwellersByVaultMock.mockImplementation(async (vaultId: string) =>
      vaultId === 'vault-a' ? roster : challengers
    )
    const vaultStore = useVaultStore()
    vaultStore.selectedVaultId = 'vault-a'
    vaultStore.vaults = [
      { id: 'vault-a', number: 42 },
      { id: 'vault-b', number: 7 },
    ] as typeof vaultStore.vaults
  })

  it('renders the Pit with the real roster and the second vault as opposition', async () => {
    const wrapper = mount(CombatZonePreview)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Vault 042')
    expect(text).toContain('Marlene Voss')
    expect(text).toContain('Curtis Abernathy')
    expect(text).toContain('Priya Nandakumar')
    expect(text).toContain('simulated bout — no server call')
    expect(text).toContain('Take the bout')
    expect(wrapper.findAll('[data-slot="progress"]')).toHaveLength(5)
    expect(getDwellersByVaultMock).toHaveBeenCalledWith('vault-b', { limit: 6 })
  })

  it('runs the simulated bout to a verdict and offers a replay', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CombatZonePreview)
    await vi.advanceTimersByTimeAsync(0)

    const takeBout = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Take the bout'))
    await takeBout?.trigger('click')
    await vi.advanceTimersByTimeAsync(900 * 6)

    expect(wrapper.text()).toContain('takes the pit')
    const replay = wrapper.findAll('button').find((button) => button.text().includes('Run again'))
    expect(replay).toBeTruthy()
    await replay?.trigger('click')
    expect(wrapper.text()).toContain('Round')
    vi.useRealTimers()
  })
})
