import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive } from 'vue'
import { createIconifyMock, createToastMock } from '../helpers/mocks'
import CombatZoneView from '@/modules/pvp/views/CombatZoneView.vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { PvpDuel } from '@/modules/pvp/services/pvpDuelService'

const route = reactive({ params: { id: 'vault-a' }, query: {} as Record<string, string> })
const api = vi.hoisted(() => ({
  list: vi.fn(),
  current: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
  accept: vi.fn(),
}))
const getDwellers = vi.hoisted(() => vi.fn())

vi.mock('vue-router', async () => ({
  ...(await vi.importActual('vue-router')),
  useRoute: () => route,
}))
vi.mock('@iconify/vue', () => createIconifyMock())
vi.mock('@/core/composables/useToast', () => ({ useToast: () => createToastMock() }))
vi.mock('@/modules/pvp/services/pvpDuelService', () => ({ pvpDuelService: api }))
vi.mock('@/modules/dwellers/services/dwellerService', () => ({ getDwellersByVault: getDwellers }))

function dweller(id: string, name: string): DwellerShort {
  return {
    id,
    first_name: name,
    last_name: '',
    level: 5,
    status: 'idle',
    combat_power: 20,
  } as DwellerShort
}

const roster = ['Ada', 'Bram', 'Cora', 'Dax'].map((name, index) => dweller(`d${index + 1}`, name))
const otherRoster = [dweller('x1', 'Xena')]
const party = {
  vault_name: 'Vault 7',
  party_size: 1,
  member_names: ['Ada'],
  power_band: 'light',
}
const posted = {
  duel_id: 'duel-open',
  status: 'OPEN',
  outcome: null,
  challenger_vault_id: 'vault-a',
  defender_vault_id: null,
  challenger_party: party,
  defender_party: null,
  journal: null,
  created_at: '2026-01-01T00:00:00Z',
  accepted_at: null,
  expires_at: '2026-01-02T00:00:00Z',
} as PvpDuel
const settled = {
  ...posted,
  duel_id: 'duel-settled',
  status: 'ACCEPTED',
  outcome: 'defender',
  defender_vault_id: 'vault-b',
  defender_party: { ...party, vault_name: 'Vault 8' },
  journal: [{ round_seq: 1, message: 'Vault 8 wins.' }],
} as PvpDuel
const boardEntry = {
  duel_id: 'duel-settled',
  challenger_vault_name: 'Vault 7',
  party_size: 1,
  member_names: ['Ada'],
  power_band: 'light',
  expires_at: '2026-01-02T00:00:00Z',
}

function mountView() {
  return mount(CombatZoneView, {
    global: {
      stubs: {
        VaultPageShell: { template: '<main><slot /></main>' },
        PageHeader: {
          props: ['title'],
          template: '<header><h1>{{ title }}</h1><slot name="actions" /></header>',
        },
      },
    },
  })
}

function button(wrapper: VueWrapper, label: string) {
  const match = wrapper.findAll('button').find((candidate) => candidate.text().includes(label))
  expect(match, `button containing ${label}`).toBeTruthy()
  return match!
}

describe('CombatZoneView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    route.params.id = 'vault-a'
    route.query = {}
    const vaultStore = useVaultStore()
    vaultStore.vaults = [
      { id: 'vault-a', number: 7 },
      { id: 'vault-b', number: 8 },
    ] as typeof vaultStore.vaults
    getDwellers.mockResolvedValue(roster)
    api.list.mockResolvedValue([boardEntry])
    api.current.mockResolvedValue(null)
    api.get.mockResolvedValue(settled)
    api.post.mockResolvedValue(posted)
    api.accept.mockResolvedValue(settled)
  })

  it('loads the roster, board and current challenge with a default party', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(api.list).toHaveBeenCalledWith('vault-a')
    expect(api.current).toHaveBeenCalledWith('vault-a')
    expect(wrapper.text()).toContain('Vault 7')
    expect(wrapper.text()).toContain('Ada')
    expect(wrapper.text()).toContain('3 / 3 selected')
    expect(button(wrapper, 'Dax').attributes('disabled')).toBeDefined()
  })

  it('posts the selected party and shows the open challenge', async () => {
    const wrapper = mountView()
    await flushPromises()
    await button(wrapper, 'Bram').trigger('click')
    await button(wrapper, 'Dax').trigger('click')
    await button(wrapper, 'Post challenge').trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('vault-a', ['d1', 'd3', 'd4'])
    expect(wrapper.text()).toContain('Your open challenge')
    expect(button(wrapper, 'Post challenge').attributes('disabled')).toBeDefined()
  })

  it('accepts a board challenge and renders the authoritative replay', async () => {
    const wrapper = mountView()
    await flushPromises()
    await button(wrapper, 'Accept').trigger('click')
    await flushPromises()

    expect(api.accept).toHaveBeenCalledWith('vault-a', 'duel-settled', ['d1', 'd2', 'd3'])
    expect(wrapper.text()).toContain('Vault 8 wins')
    expect(wrapper.text()).toContain('Authoritative result and replay from the server.')
    expect(wrapper.text()).toContain('No challenges are waiting')
  })

  it('restores the server-owned open challenge on any device', async () => {
    api.current.mockResolvedValue(posted)
    const wrapper = mountView()
    await flushPromises()

    expect(api.current).toHaveBeenCalledWith('vault-a')
    expect(api.get).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Your open challenge')
  })

  it('opens a duel linked from a notification', async () => {
    route.query = { duel: 'duel-settled' }
    const wrapper = mountView()
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('vault-a', 'duel-settled')
    expect(wrapper.text()).toContain('Vault 8 wins')
  })

  it('ignores a delayed duel read from the previous vault', async () => {
    route.query = { duel: 'duel-settled' }
    let resolveDuel!: (value: PvpDuel) => void
    api.get.mockImplementation(
      () =>
        new Promise<PvpDuel>((resolve) => {
          resolveDuel = resolve
        })
    )
    const wrapper = mountView()
    await vi.waitFor(() => expect(api.get).toHaveBeenCalled())
    route.params.id = 'vault-b'
    route.query = {}
    await flushPromises()
    resolveDuel(settled)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Vault 8 wins')
  })

  it('does not apply a posted challenge after the vault changes', async () => {
    let resolvePost!: (value: PvpDuel) => void
    api.post.mockImplementation(
      () =>
        new Promise<PvpDuel>((resolve) => {
          resolvePost = resolve
        })
    )
    const wrapper = mountView()
    await flushPromises()
    await button(wrapper, 'Post challenge').trigger('click')
    route.params.id = 'vault-b'
    await flushPromises()
    resolvePost(posted)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Your open challenge')
  })

  it('ignores a roster response from the previous vault', async () => {
    let resolveFirst!: (value: DwellerShort[]) => void
    getDwellers.mockImplementation((id: string) =>
      id === 'vault-a'
        ? new Promise<DwellerShort[]>((resolve) => {
            resolveFirst = resolve
          })
        : Promise.resolve(otherRoster)
    )
    const wrapper = mountView()
    route.params.id = 'vault-b'
    await flushPromises()
    resolveFirst(roster)
    await flushPromises()

    expect(wrapper.text()).toContain('Xena')
    expect(wrapper.text()).not.toContain('Bram')
  })
})
