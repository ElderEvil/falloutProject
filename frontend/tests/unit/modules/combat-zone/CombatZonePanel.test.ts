import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, nextTick, onMounted } from 'vue'
import CombatZonePanel from '@/modules/combat-zone/components/CombatZonePanel.vue'
import { useCombatZoneStore } from '@/modules/combat-zone/stores/combatZone'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { DWELLER_LIST_CHANGED_MESSAGE } from '@/modules/dwellers/stores/dwellerFilter'
import * as combatZoneService from '@/modules/combat-zone/api/combatZoneService'
import type {
  CombatZoneHistoryEntry,
  CombatZoneMatchRead,
} from '@/modules/combat-zone/models/combatZone'
import { createToastMock } from '../../helpers/mocks'

vi.mock('@/modules/combat-zone/api/combatZoneService')

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

const lobby = {
  enabled: true,
  server_time: '2026-10-19T18:00:00Z',
  entry_fee_caps: 100,
  travel_seconds: 60,
  queued: [],
  active_matches: [],
}

const fighter = {
  id: 'dweller-1',
  name: 'Test Dweller',
  level: 5,
  health: 100,
  max_health: 100,
  power: 42,
}

const finishedMatch = {
  id: 'match-1',
  status: 'finished',
  round_seq: 4,
  next_attack_party: 'A',
  pot_caps: 200,
  party_a: {
    fighter,
    party_id: 'party-1',
    vault_id: 'vault-a',
    vault_number: 101,
    dweller_id: 'dweller-1',
    stance: 'defensive',
    is_winner: true,
    credited_caps: 200,
  },
  party_b: {
    fighter: { ...fighter, id: 'dweller-2', name: 'Other Dweller', health: 0 },
    party_id: 'party-2',
    vault_id: 'vault-b',
    vault_number: 202,
    dweller_id: 'dweller-2',
    stance: 'defensive',
    is_winner: false,
    credited_caps: null,
  },
  events: [],
  cursor: { sequence: 4, round_seq: 4, status: 'finished' },
} as unknown as CombatZoneMatchRead

const historyEntry = {
  match_id: 'match-1',
  finish_reason: 'victory',
  pot_caps: 200,
  round_seq: 4,
  winner_party_id: 'party-1',
  party_a: finishedMatch.party_a,
  party_b: finishedMatch.party_b,
  started_at: null,
  finished_at: null,
} as unknown as CombatZoneHistoryEntry

function mountPanel(vaultId = 'vault-a') {
  return mount(CombatZonePanel, {
    props: {
      open: true,
      vaultId,
      marker: { enabled: true } as never,
      initialMatchId: null,
    },
    global: {
      stubs: {
        TerminalModal: { template: '<div><slot /><slot name="footer" /></div>' },
        CombatZoneMatch: true,
        Button: { template: '<button><slot /></button>' },
        Icon: true,
      },
    },
  })
}

describe('Combat Zone panel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(combatZoneService.getLobby).mockResolvedValue(lobby)
    vi.mocked(combatZoneService.getParty).mockResolvedValue(null)
    vi.mocked(combatZoneService.getHistory).mockResolvedValue([])
    vi.mocked(combatZoneService.getMatch).mockResolvedValue(finishedMatch)
    useAuthStore().token = 'test-token'
    useVaultStore().loadedVaults['vault-a'] = { number: 101, bottle_caps: 1_000 } as never
    useVaultStore().loadedVaults['vault-b'] = { number: 202, bottle_caps: 1_000 } as never
    const filter = useDwellerStore().filter
    filter.allDwellers = []
    filter.fetchAllDwellers = vi.fn().mockResolvedValue(undefined)
  })

  it('remounts playback when a replay switches to a different bout', async () => {
    let mounts = 0
    const MatchStub = defineComponent({
      name: 'CombatZoneMatch',
      props: ['match', 'viewerVaultId', 'replay'],
      emits: ['stance', 'back'],
      setup() {
        onMounted(() => {
          mounts += 1
        })
        return {}
      },
      template: '<div class="match-stub">{{ match.id }}</div>',
    })
    vi.mocked(combatZoneService.getHistory).mockResolvedValue([historyEntry])
    const wrapper = mount(CombatZonePanel, {
      props: {
        open: true,
        vaultId: 'vault-a',
        marker: { enabled: true } as never,
        initialMatchId: null,
      },
      global: {
        stubs: {
          TerminalModal: { template: '<div><slot /><slot name="footer" /></div>' },
          CombatZoneMatch: MatchStub,
          Button: { template: '<button><slot /></button>' },
          Icon: true,
        },
      },
    })
    await flushPromises()

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('The frequency'))
      ?.trigger('click')
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Replay')
      ?.trigger('click')
    await flushPromises()
    expect(mounts).toBe(1)

    const store = useCombatZoneStore()
    store.match = { ...finishedMatch, id: 'match-2' } as CombatZoneMatchRead
    await nextTick()

    expect(mounts).toBe(2)
    wrapper.unmount()
  })

  it('does not report a stale roster error for the new vault', async () => {
    let rejectFirst!: (error: Error) => void
    const first = new Promise<void>((_, reject) => {
      rejectFirst = reject
    })
    const filter = useDwellerStore().filter
    vi.mocked(filter.fetchAllDwellers).mockReturnValueOnce(first).mockResolvedValueOnce(undefined)

    const wrapper = mountPanel('vault-a')
    await flushPromises()
    await wrapper.setProps({ vaultId: 'vault-b' })
    await flushPromises()
    rejectFirst(new Error(DWELLER_LIST_CHANGED_MESSAGE))
    await flushPromises()

    expect(wrapper.text()).not.toContain('Roster for vault vault-b')
    wrapper.unmount()
  })

  it('still opens a frozen result when the roster request fails', async () => {
    const filter = useDwellerStore().filter
    vi.mocked(filter.fetchAllDwellers).mockRejectedValueOnce(new Error('network down'))
    const wrapper = mount(CombatZonePanel, {
      props: {
        open: true,
        vaultId: 'vault-a',
        marker: null,
        initialMatchId: 'match-1',
      },
      global: {
        stubs: {
          TerminalModal: { template: '<div><slot /><slot name="footer" /></div>' },
          CombatZoneMatch: {
            template: '<div class="match-stub">{{ match.id }}</div>',
            props: ['match'],
          },
          Button: { template: '<button><slot /></button>' },
          Icon: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('.match-stub').text()).toBe('match-1')
    expect(combatZoneService.getMatch).toHaveBeenCalledWith('test-token', 'match-1')
    wrapper.unmount()
  })

  it('ignores a roster rejection after the same vault is reopened', async () => {
    let rejectFirst!: (error: Error) => void
    const first = new Promise<void>((_, reject) => {
      rejectFirst = reject
    })
    const filter = useDwellerStore().filter
    vi.mocked(filter.fetchAllDwellers).mockReturnValueOnce(first).mockResolvedValueOnce(undefined)

    const wrapper = mountPanel('vault-a')
    await flushPromises()
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    await flushPromises()
    rejectFirst(new Error(DWELLER_LIST_CHANGED_MESSAGE))
    await flushPromises()

    expect(wrapper.text()).not.toContain('Roster for vault vault-a')
    wrapper.unmount()
  })

  it('ignores a roster rejection after the account session changes', async () => {
    let rejectFirst!: (error: Error) => void
    const first = new Promise<void>((_, reject) => {
      rejectFirst = reject
    })
    const filter = useDwellerStore().filter
    vi.mocked(filter.fetchAllDwellers).mockReturnValueOnce(first)

    const wrapper = mountPanel('vault-a')
    await flushPromises()
    useAuthStore().sessionGeneration++
    rejectFirst(new Error(DWELLER_LIST_CHANGED_MESSAGE))
    await flushPromises()

    expect(wrapper.text()).not.toContain('Roster for vault vault-a')
    wrapper.unmount()
  })

  it('surfaces a generic roster load failure for the current vault', async () => {
    const filter = useDwellerStore().filter
    vi.mocked(filter.fetchAllDwellers).mockRejectedValueOnce(new Error('network down'))

    const wrapper = mountPanel('vault-a')
    await flushPromises()

    expect(wrapper.text()).toContain('Roster for vault vault-a failed to load. Retry.')
    wrapper.unmount()
  })
})
