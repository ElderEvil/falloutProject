import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
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

const GATE_WINDOW_MS = 90_000
const ROUND_INTERVAL_MS = 900

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

function findTakeBout(wrapper: VueWrapper) {
  return wrapper.findAll('button').find((button) => button.text().includes('Take the bout'))
}

/** The bout header renders the round number as the sibling of its "Round" label. */
function roundNumber(wrapper: VueWrapper): string | null | undefined {
  const label = wrapper.findAll('p').find((node) => node.text() === 'Round')
  return label?.element.nextElementSibling?.textContent?.trim()
}

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

  afterEach(() => {
    vi.useRealTimers()
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
    expect(text).toContain('Opposing vault')
    expect(text).not.toContain('Stand-in trio')
    expect(text).toContain('Take the bout')
    expect(wrapper.findAll('[data-slot="progress"]')).toHaveLength(5)
    expect(getDwellersByVaultMock).toHaveBeenCalledWith('vault-b', { limit: 6 })
  })

  it('keeps the bout button disabled until the seal clock opens the gate', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CombatZonePreview)
    await vi.advanceTimersByTimeAsync(0)

    expect(wrapper.text()).toContain('The gate opens in 01:30')
    expect(findTakeBout(wrapper)?.attributes('disabled')).toBeDefined()

    // One second short of the window: the countdown and the button agree.
    await vi.advanceTimersByTimeAsync(GATE_WINDOW_MS - 1_000)
    expect(wrapper.text()).toContain('The gate opens in 00:01')
    expect(findTakeBout(wrapper)?.attributes('disabled')).toBeDefined()

    await vi.advanceTimersByTimeAsync(1_000)

    expect(wrapper.text()).not.toContain('The gate opens in')
    expect(findTakeBout(wrapper)?.attributes('disabled')).toBeUndefined()
  })

  it('disables the bout and shows the empty state when the roster is empty', async () => {
    const vaultStore = useVaultStore()
    vaultStore.vaults = [{ id: 'vault-a', number: 42 }] as typeof vaultStore.vaults
    getDwellersByVaultMock.mockImplementation(async () => [])

    vi.useFakeTimers()
    const wrapper = mount(CombatZonePreview)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(GATE_WINDOW_MS)

    expect(wrapper.text()).toContain('No roster to draw from')
    expect(findTakeBout(wrapper)?.attributes('disabled')).toBeDefined()
  })

  it('runs the simulated bout to a verdict and offers a replay', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CombatZonePreview)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(GATE_WINDOW_MS)

    await findTakeBout(wrapper)?.trigger('click')
    await vi.advanceTimersByTimeAsync(ROUND_INTERVAL_MS * 6)

    expect(wrapper.text()).toContain('takes the pit')
    const replay = wrapper.findAll('button').find((button) => button.text().includes('Run again'))
    expect(replay).toBeTruthy()
    await replay?.trigger('click')
    expect(wrapper.text()).toContain('Round')
  })

  it('ignores an opposition fetch that lands after the bout has started', async () => {
    vi.useFakeTimers()
    let resolveOpposition: (value: DwellerShort[]) => void = () => {}
    const deferred = new Promise<DwellerShort[]>((resolve) => {
      resolveOpposition = resolve
    })
    getDwellersByVaultMock.mockImplementation((vaultId: string) =>
      vaultId === 'vault-a' ? Promise.resolve(roster) : deferred
    )

    const wrapper = mount(CombatZonePreview)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(GATE_WINDOW_MS)

    await findTakeBout(wrapper)?.trigger('click')
    expect(wrapper.text()).toContain('Bout card is live')

    resolveOpposition(challengers)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(ROUND_INTERVAL_MS)

    expect(wrapper.text()).toContain('Bout card is live')
    expect(wrapper.text()).toContain('Stand-in trio')
    expect(wrapper.text()).not.toContain('Opposing vault')
    expect(wrapper.text()).not.toContain('Priya Nandakumar')
    expect(roundNumber(wrapper)).toBe('01')
  })

  it('stops advancing rounds and journal lines once the verdict lands', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CombatZonePreview)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(GATE_WINDOW_MS)

    await findTakeBout(wrapper)?.trigger('click')
    await vi.advanceTimersByTimeAsync(ROUND_INTERVAL_MS * 6)
    expect(wrapper.text()).toContain('takes the pit')

    const roundAtVerdict = roundNumber(wrapper)
    const journalAtVerdict = wrapper.findAll('ol li').length
    expect(roundAtVerdict ?? '').toMatch(/^\d{2}$/)
    expect(journalAtVerdict).toBeGreaterThan(0)

    await vi.advanceTimersByTimeAsync(ROUND_INTERVAL_MS * 20)

    expect(roundNumber(wrapper)).toBe(roundAtVerdict)
    expect(wrapper.findAll('ol li')).toHaveLength(journalAtVerdict)
  })

  it('clears the clock and the round interval when unmounted mid-bout', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CombatZonePreview)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(GATE_WINDOW_MS)

    await findTakeBout(wrapper)?.trigger('click')
    await vi.advanceTimersByTimeAsync(ROUND_INTERVAL_MS)
    expect(roundNumber(wrapper)).toBe('01')
    expect(vi.getTimerCount()).toBeGreaterThan(0)

    wrapper.unmount()

    expect(vi.getTimerCount()).toBe(0)
  })
})
