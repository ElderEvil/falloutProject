import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createIconifyMock, createToastMock } from '../../helpers/mocks'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ArenaModal from '@/modules/rooms/components/ArenaModal.vue'
import type { ArenaRoomState } from '@/modules/rooms/api/arena'

const mockToast = createToastMock()

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<div class="mock-icon" :data-icon="icon"></div>' })
)

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

vi.mock('@/core/composables/usePolling', () => ({
  usePolling: () => vi.fn(),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    management: { unassignDwellerFromRoom: vi.fn().mockResolvedValue({}) },
  }),
}))

const storeMock = vi.hoisted(() => {
  const alpha = { id: 'a-1', name: 'Alpha Dweller', level: 10, health: 80, max_health: 100, power: 42, is_creature: false }
  const bravo = { id: 'b-1', name: 'Bravo Dweller', level: 8, health: 90, max_health: 100, power: 35, is_creature: false }
  const charlie = { id: 'c-1', name: 'Charlie Dweller', level: 7, health: 80, max_health: 100, power: 30, is_creature: false }
  const delta = { id: 'd-1', name: 'Delta Dweller', level: 9, health: 70, max_health: 100, power: 33, is_creature: false }
  const echo = { id: 'e-1', name: 'Echo Dweller', level: 6, health: 60, max_health: 100, power: 20, is_creature: false }

  const asRoster = (fighter: typeof alpha) => ({
    id: fighter.id,
    name: fighter.name,
    level: fighter.level,
    health: fighter.health,
    max_health: fighter.max_health,
  })

  const readyRoom: ArenaRoomState = {
    room_id: 'room-1',
    room_name: 'Arena',
    tier: 1,
    mode: 'duel',
    fighter_a_id: 'a-1',
    fighter_b_id: 'b-1',
    fighters: [alpha, bravo],
    team_a: [alpha],
    team_b: [bravo],
    roster: [asRoster(alpha), asRoster(bravo), asRoster(charlie), asRoster(delta), asRoster(echo)],
    fight_ready: true,
    match_done: false,
    fight_started: false,
    countdown_remaining: 0,
    can_start: true,
    winner_name: null,
    events: [],
  }
  return {
    currentRoom: readyRoom as ArenaRoomState | null,
    fetchState: vi.fn(),
    setFighters: vi.fn(),
    readyRoom,
  }
})

vi.mock('@/modules/rooms/stores/arena', () => ({
  useArenaStore: () => ({
    getRoom: () => storeMock.currentRoom,
    fetchState: storeMock.fetchState,
    setFighters: storeMock.setFighters,
    startFight: vi.fn().mockResolvedValue(true),
    clearEvents: vi.fn().mockResolvedValue(true),
    reset: vi.fn(),
  }),
}))

const mountModal = () =>
  mount(ArenaModal, {
    props: { vaultId: 'vault-1', roomId: 'room-1' },
    global: { plugins: [createPinia()] },
  })

const modeButton = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('.mode-select button').find((button) => button.text() === label)!

const slots = (wrapper: VueWrapper) => wrapper.findAll('.fighter-slot')

const openPicker = async (wrapper: VueWrapper, slotIndex: number) => {
  const slot = slots(wrapper)[slotIndex]
  await slot.get('.fighter-slot-empty').trigger('click')
  await flushPromises()
  return slot
}

const pickOption = async (slot: ReturnType<typeof slots>[number], name: string) => {
  const option = slot.findAll('.picker-option').find((candidate) => candidate.text().includes(name))!
  await option.trigger('click')
  await flushPromises()
}

describe('ArenaModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeMock.currentRoom = storeMock.readyRoom
    storeMock.fetchState.mockReset().mockResolvedValue(true)
    storeMock.setFighters.mockReset().mockResolvedValue(true)
  })

  it('renders fighter slots with names and power', async () => {
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Alpha Dweller')
    expect(wrapper.text()).toContain('Bravo Dweller')
    expect(wrapper.text()).toContain('POW 42')
    expect(storeMock.fetchState).toHaveBeenCalledWith('vault-1', 'test-token', false)
  })

  it('shows START FIGHT when the room is ready', async () => {
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('START FIGHT')
    expect(wrapper.text()).toContain('READY')
  })

  it('offers duel and brawl modes with the active one pressed', async () => {
    const wrapper = mountModal()
    await flushPromises()

    const buttons = wrapper.findAll('.mode-select button')
    expect(buttons.map((button) => button.text())).toEqual(['DUEL', 'BRAWL'])
    expect(buttons[0].attributes('aria-pressed')).toBe('true')
    expect(buttons[1].attributes('aria-pressed')).toBe('false')
  })

  it('labels readiness with the mode-sized fighter count', async () => {
    storeMock.currentRoom = { ...storeMock.readyRoom, can_start: false }
    const duel = mountModal()
    await flushPromises()
    expect(duel.text()).toContain('NEEDS 2 FIGHTERS')

    storeMock.currentRoom = { ...storeMock.readyRoom, mode: 'brawl', can_start: false }
    const brawl = mountModal()
    await flushPromises()
    expect(brawl.text()).toContain('NEEDS 4 FIGHTERS')
  })

  it('switches to brawl with two slots per team', async () => {
    const wrapper = mountModal()
    await flushPromises()
    expect(slots(wrapper)).toHaveLength(2)

    await modeButton(wrapper, 'BRAWL').trigger('click')
    await flushPromises()

    expect(slots(wrapper)).toHaveLength(4)
    expect(wrapper.findAll('.team-label').map((label) => label.text())).toEqual(['TEAM A', 'TEAM B'])
    expect(storeMock.setFighters).not.toHaveBeenCalled()
  })

  it('fills the brawl slots without duplicating a dweller and persists the four ids', async () => {
    const wrapper = mountModal()
    await flushPromises()
    await modeButton(wrapper, 'BRAWL').trigger('click')
    await flushPromises()

    const secondA = await openPicker(wrapper, 1)
    const secondAOptions = secondA.findAll('.picker-option').map((option) => option.text())
    expect(secondAOptions.some((text) => text.includes('Alpha Dweller'))).toBe(false)
    expect(secondAOptions.some((text) => text.includes('Bravo Dweller'))).toBe(false)
    await pickOption(secondA, 'Charlie Dweller')
    expect(storeMock.setFighters).not.toHaveBeenCalled()

    const secondB = await openPicker(wrapper, 3)
    const secondBOptions = secondB.findAll('.picker-option').map((option) => option.text())
    expect(secondBOptions.some((text) => text.includes('Charlie Dweller'))).toBe(false)
    await pickOption(secondB, 'Delta Dweller')

    expect(storeMock.setFighters).toHaveBeenCalledTimes(1)
    expect(storeMock.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      { mode: 'brawl', fighterAId: 'a-1', fighterBId: 'b-1', fighterCId: 'c-1', fighterDId: 'd-1' },
      'test-token'
    )
  })

  it('auto-fills the last empty brawl slot when one candidate remains', async () => {
    storeMock.currentRoom = { ...storeMock.readyRoom, roster: storeMock.readyRoom.roster.slice(0, 4) }
    const wrapper = mountModal()
    await flushPromises()
    await modeButton(wrapper, 'BRAWL').trigger('click')
    await flushPromises()

    const secondA = await openPicker(wrapper, 1)
    await pickOption(secondA, 'Charlie Dweller')

    expect(storeMock.setFighters).toHaveBeenCalledTimes(1)
    expect(storeMock.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      { mode: 'brawl', fighterAId: 'a-1', fighterBId: 'b-1', fighterCId: 'c-1', fighterDId: 'd-1' },
      'test-token'
    )
  })

  it('returns to duel with a duel payload when switching back', async () => {
    const wrapper = mountModal()
    await flushPromises()
    await modeButton(wrapper, 'BRAWL').trigger('click')
    await flushPromises()
    await modeButton(wrapper, 'DUEL').trigger('click')
    await flushPromises()

    expect(storeMock.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      { mode: 'duel', fighterAId: 'a-1', fighterBId: 'b-1', fighterCId: null, fighterDId: null },
      'test-token'
    )
    expect(slots(wrapper)).toHaveLength(2)
  })

  it('keeps room-management actions out of the battle panel', async () => {
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.find('.arena-management').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Unassign All Dwellers')
    expect(wrapper.text()).not.toContain('Destroy Room')
  })

  it('shows a retry state when loading the arena fails', async () => {
    storeMock.fetchState.mockResolvedValueOnce(false)
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Unable to load Arena status.')
    await wrapper.get('button').trigger('click')
    expect(storeMock.fetchState).toHaveBeenCalledTimes(2)
  })

  it('shows the winner banner when a match is done', async () => {
    storeMock.currentRoom = { ...storeMock.readyRoom, match_done: true, winner_name: 'Alpha Dweller' }
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('MATCH COMPLETE')
    expect(wrapper.text()).toContain('Alpha Dweller wins')
  })

  it('renders the battle journal oldest-first with round numbers and grouping', async () => {
    storeMock.currentRoom = {
      ...storeMock.readyRoom,
      events: [
        { id: 'e4', round_seq: 4, kind: 'finish', message: 'Alpha Dweller defeated Bravo Dweller!' },
        { id: 'e3', round_seq: 3, kind: 'hit', message: 'Alpha Dweller hits Bravo Dweller for 5' },
        { id: 'e2', round_seq: 2, kind: 'hit', message: 'Alpha Dweller hits Bravo Dweller for 5' },
        { id: 'e1', round_seq: 1, kind: 'hit', message: 'Bravo Dweller hits Alpha Dweller for 3' },
      ],
    }
    const wrapper = mountModal()
    await flushPromises()

    const items = wrapper.findAll('[aria-label="Battle log"] li')
    expect(items).toHaveLength(3)
    expect(items[0].text()).toContain('Bravo Dweller hits Alpha Dweller for 3')
    expect(items[0].text()).toContain('R1')
    expect(items[1].text()).toContain('Alpha Dweller hits Bravo Dweller for 5')
    expect(items[1].text()).toContain('R2')
    expect(items[1].text()).toContain('×2')
    expect(items[2].text()).toContain('FINISH')
    expect(items[2].text()).toContain('R4')
  })

  it('shows a polite empty state when no rounds have been fought', async () => {
    const wrapper = mountModal()
    await flushPromises()

    const journal = wrapper.get('[aria-label="Battle log"]')
    expect(journal.attributes('aria-live')).toBe('polite')
    expect(journal.text()).toContain('No rounds fought yet.')
  })
})
