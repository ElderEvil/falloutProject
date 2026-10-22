import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { computed, ref } from 'vue'
import { createIconifyMock, createToastMock } from '../../helpers/mocks'
import { mount, flushPromises, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useDwellerMedicalStore } from '@/modules/dwellers/stores/dwellerMedical'
import { useVaultStore } from '@/modules/vault/stores/vault'
import ArenaModal from '@/modules/rooms/components/ArenaModal.vue'
import type { ArenaRoomState } from '@/modules/rooms/api/arena'

enableAutoUnmount(afterEach)

const mockToast = createToastMock()

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<div class="mock-icon" :data-icon="icon"></div>' })
)

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    management: { unassignDwellerFromRoom: vi.fn().mockResolvedValue({}) },
  }),
}))

const storeMock = vi.hoisted(() => {
  const alpha = {
    id: 'a-1',
    name: 'Alpha Dweller',
    level: 10,
    health: 80,
    max_health: 100,
    power: 42,
    is_creature: false,
  }
  const bravo = {
    id: 'b-1',
    name: 'Bravo Dweller',
    level: 8,
    health: 90,
    max_health: 100,
    power: 35,
    is_creature: false,
  }
  const charlie = {
    id: 'c-1',
    name: 'Charlie Dweller',
    level: 7,
    health: 80,
    max_health: 100,
    power: 30,
    is_creature: false,
  }
  const delta = {
    id: 'd-1',
    name: 'Delta Dweller',
    level: 9,
    health: 70,
    max_health: 100,
    power: 33,
    is_creature: false,
  }
  const echo = {
    id: 'e-1',
    name: 'Echo Dweller',
    level: 6,
    health: 60,
    max_health: 100,
    power: 20,
    is_creature: false,
  }

  const radroach = {
    id: 'radroach-swarm#0',
    name: 'Radroach swarm',
    level: 0,
    health: 35,
    max_health: 35,
    power: 35,
    is_creature: true,
  }
  const deathclaw = {
    id: 'deathclaw#0',
    name: 'Deathclaw',
    level: 0,
    health: 120,
    max_health: 120,
    power: 120,
    is_creature: true,
  }

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
    tier: 3,
    available_modes: ['duel', 'brawl', 'hunt'],
    mode: 'duel',
    next_attack_team: 'A',
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

  const huntRoom: ArenaRoomState = {
    ...readyRoom,
    mode: 'hunt',
    fighter_b_id: null,
    fighters: [alpha, radroach],
    team_b: [radroach],
  }

  return {
    currentRoom: readyRoom as ArenaRoomState | null,
    fetchState: vi.fn(),
    setFighters: vi.fn(),
    fetchCreatures: vi.fn(),
    queueSkill: vi.fn().mockResolvedValue(true),
    creatures: [
      { key: 'training-eyebot', name: 'Training Eyebot', power: 30, max_hp: 20, is_robot: true },
      {
        key: 'training-mr-handy',
        name: 'Training Mr. Handy',
        power: 20,
        max_hp: 30,
        is_robot: true,
      },
      {
        key: 'training-protectron',
        name: 'Training Protectron',
        power: 10,
        max_hp: 60,
        is_robot: true,
      },
      { key: 'radroach-swarm', name: 'Radroach swarm', power: 35, max_hp: 35 },
      { key: 'deathclaw', name: 'Deathclaw', power: 120, max_hp: 120 },
      { key: 'bloatfly', name: 'Bloatfly', power: 10, max_hp: 10 },
      { key: 'mole-rat-pack', name: 'Mole Rat pack', power: 20, max_hp: 20 },
      { key: 'night-stalker', name: 'Night Stalker', power: 30, max_hp: 30 },
      { key: 'mirelurk', name: 'Mirelurk', power: 40, max_hp: 40 },
      { key: 'yao-guai', name: 'Yao Guai', power: 40, max_hp: 40 },
    ],
    readyRoom,
    huntRoom,
  }
})

vi.mock('@/modules/rooms/stores/arena', () => ({
  useArenaStore: () => ({
    getRoom: () => storeMock.currentRoom,
    fetchState: storeMock.fetchState,
    setFighters: storeMock.setFighters,
    fetchCreatures: storeMock.fetchCreatures,
    creatures: storeMock.creatures,
    startFight: vi.fn().mockResolvedValue(true),
    queueSkill: storeMock.queueSkill,
    clearEvents: vi.fn().mockResolvedValue(true),
    reset: vi.fn(),
  }),
}))

const roomState = ref<ArenaRoomState | null>(storeMock.readyRoom)
const controller = {
  roomState: computed(() => roomState.value),
  isLoading: ref(false),
  loadFailed: ref(false),
  pendingSkills: ref(new Set<string>()),
  damageNumbers: ref<Array<{ id: number; fighterId: string; amount: number }>>([]),
  attackingTeam: ref<'A' | 'B' | null>(null),
  skillBurst: ref<{ id: string; message: string } | null>(null),
  load: vi.fn(),
  retry: vi.fn(),
  refresh: vi.fn().mockResolvedValue(undefined),
  queueSkill: vi.fn(),
  startFight: vi.fn().mockResolvedValue(true),
  resetDamageTracking: vi.fn(),
}

const mountModal = () =>
  mount(ArenaModal, {
    props: { vaultId: 'vault-1', roomId: 'room-1', controller },
    global: { plugins: [createPinia()] },
  })

const modeTabs = (wrapper: VueWrapper) => wrapper.findAll('[role="tab"]')
const chooseMode = async (wrapper: VueWrapper, label: string) => {
  const tab = modeTabs(wrapper).find((tab) => tab.text().toUpperCase() === label)!
  await tab.trigger('keydown', { key: 'Enter' })
  await flushPromises()
}

const slots = (wrapper: VueWrapper) => wrapper.findAll('.fighter-slot')

const openPicker = async (wrapper: VueWrapper, slotIndex: number) => {
  const slot = slots(wrapper)[slotIndex]
  await slot.get('.fighter-slot-empty').trigger('click')
  await flushPromises()
  return slot
}

const pickOption = async (slot: ReturnType<typeof slots>[number], name: string) => {
  const option = slot
    .findAll('.picker-option')
    .find((candidate) => candidate.text().includes(name))!
  await option.trigger('click')
  await flushPromises()
}

describe('ArenaModal', () => {
  it.each([
    [1, ['duel'], true, true],
    [2, ['duel', 'brawl'], false, true],
    [3, ['duel', 'brawl', 'hunt'], false, false],
  ] as const)(
    'shows the server mode unlocks at tier %i',
    async (tier, availableModes, brawlLocked, huntLocked) => {
      roomState.value = { ...storeMock.readyRoom, tier, available_modes: [...availableModes] }
      const wrapper = mountModal()
      await flushPromises()
      const options = modeTabs(wrapper)
      expect(options[0].attributes('disabled')).toBeUndefined()
      expect(options[1].attributes('disabled') !== undefined).toBe(brawlLocked)
      expect(options[2].attributes('disabled') !== undefined).toBe(huntLocked)
    }
  )

  beforeEach(() => {
    setActivePinia(createPinia())
    roomState.value = storeMock.readyRoom
    controller.isLoading.value = false
    controller.loadFailed.value = false
    controller.retry.mockClear()
    controller.refresh.mockClear()
    controller.startFight.mockClear()
    controller.resetDamageTracking.mockClear()
    storeMock.setFighters.mockReset().mockResolvedValue(true)
    storeMock.fetchCreatures.mockReset().mockResolvedValue(true)
  })

  it('explains assignment before offering match slots for an empty roster', async () => {
    roomState.value = {
      ...storeMock.readyRoom,
      roster: [],
      fighter_a_id: null,
      fighter_b_id: null,
      fighters: [],
      team_a: [],
      team_b: [],
      can_start: false,
    }
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Assign adult dwellers to the Arena to build a roster.')
    expect(wrapper.find('.fighter-slot-empty').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('START FIGHT')
  })

  it('shows useful bench details without duplicating selected fighters', async () => {
    const wrapper = mountModal()
    await flushPromises()
    const bench = wrapper.get('[aria-label="Arena bench"]')
    expect(bench.text()).toContain('Charlie Dweller')
    expect(bench.text()).toContain('Level 7')
    expect(bench.text()).toContain('80 / 100 HP')
    expect(bench.text()).not.toContain('Alpha Dweller')
    expect(bench.findAll('[role="progressbar"]')).toHaveLength(3)
    expect(
      bench.findAll('[role="progressbar"]').every((bar) => !!bar.attributes('aria-label'))
    ).toBe(true)
  })

  it('renders fighter slots with names and power', async () => {
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Alpha Dweller')
    expect(wrapper.text()).toContain('Bravo Dweller')
    expect(wrapper.text()).toContain('POW 42')
  })

  it('shows START FIGHT when the room is ready', async () => {
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('START FIGHT')
    expect(wrapper.text()).toContain('READY')
  })

  it('shows all match modes as tabs with the current mode selected', async () => {
    const wrapper = mountModal()
    await flushPromises()
    expect(wrapper.get('[role="tablist"]').attributes('aria-label')).toBe('Match mode')
    const tabs = modeTabs(wrapper)
    expect(tabs.map((tab) => tab.text())).toEqual(['Duel', 'Brawl', 'Hunt'])
    expect(tabs.map((tab) => tab.attributes('aria-selected'))).toEqual(['true', 'false', 'false'])
    expect(wrapper.get('[role="tabpanel"]').attributes('aria-labelledby')).toBe(
      tabs[0].attributes('id')
    )
  })

  it('labels readiness with the mode-sized fighter count', async () => {
    roomState.value = { ...storeMock.readyRoom, can_start: false }
    const duel = mountModal()
    await flushPromises()
    expect(duel.text()).toContain('NEEDS 2 FIGHTERS')

    roomState.value = { ...storeMock.readyRoom, mode: 'brawl', can_start: false }
    const brawl = mountModal()
    await flushPromises()
    expect(brawl.text()).toContain('NEEDS 3 DWELLERS + A PARTNER')
  })

  it('switches to brawl with two slots per team', async () => {
    const wrapper = mountModal()
    await flushPromises()
    expect(slots(wrapper)).toHaveLength(2)

    await chooseMode(wrapper, 'BRAWL')
    await flushPromises()

    expect(slots(wrapper)).toHaveLength(4)
    expect(wrapper.findAll('.team-label').map((label) => label.text())).toEqual([
      'TEAM A',
      'TEAM B',
    ])
    expect(storeMock.setFighters).not.toHaveBeenCalled()
  })

  it('keeps roster portraits on the bench and in pending brawl selections', async () => {
    roomState.value = {
      ...storeMock.readyRoom,
      roster: storeMock.readyRoom.roster.map((entry) => ({
        ...entry,
        thumbnail_url: `/static/portraits/${entry.id}.png`,
      })),
    }
    const wrapper = mountModal()
    await flushPromises()
    expect(
      wrapper.get('[aria-label="Arena bench"] img[alt="Charlie Dweller"]').attributes('src')
    ).toContain('/static/portraits/c-1.png')
    await chooseMode(wrapper, 'BRAWL')
    const picker = await openPicker(wrapper, 1)
    await pickOption(picker, 'Charlie Dweller')
    expect(slots(wrapper)[1].get('img').attributes('src')).toContain('/static/portraits/c-1.png')
    expect(storeMock.setFighters).not.toHaveBeenCalled()
  })

  it('fills the brawl slots without duplicating a dweller and persists the four ids', async () => {
    const wrapper = mountModal()
    await flushPromises()
    await chooseMode(wrapper, 'BRAWL')
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
      {
        mode: 'brawl',
        fighterAId: 'a-1',
        fighterBId: 'b-1',
        fighterCId: 'c-1',
        fighterDId: 'd-1',
        teamABotKey: null,
        teamBBotKey: null,
      },
      'test-token'
    )
  })

  it('auto-fills the last empty brawl slot when one candidate remains', async () => {
    roomState.value = {
      ...storeMock.readyRoom,
      roster: storeMock.readyRoom.roster.slice(0, 4),
    }
    const wrapper = mountModal()
    await flushPromises()
    await chooseMode(wrapper, 'BRAWL')
    await flushPromises()

    const secondA = await openPicker(wrapper, 1)
    await pickOption(secondA, 'Charlie Dweller')

    expect(storeMock.setFighters).toHaveBeenCalledTimes(1)
    expect(storeMock.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      {
        mode: 'brawl',
        fighterAId: 'a-1',
        fighterBId: 'b-1',
        fighterCId: 'c-1',
        fighterDId: 'd-1',
        teamABotKey: null,
        teamBBotKey: null,
      },
      'test-token'
    )
  })

  it('returns to duel with a duel payload when switching back', async () => {
    const wrapper = mountModal()
    await flushPromises()
    await chooseMode(wrapper, 'BRAWL')
    await flushPromises()
    await chooseMode(wrapper, 'DUEL')
    await flushPromises()

    expect(storeMock.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      {
        mode: 'duel',
        fighterAId: 'a-1',
        fighterBId: 'b-1',
        fighterCId: null,
        fighterDId: null,
        teamABotKey: null,
        teamBBotKey: null,
      },
      'test-token'
    )
    expect(slots(wrapper)).toHaveLength(2)
  })

  it('switches to hunt with dweller slots on team A and a creature picker on team B', async () => {
    const wrapper = mountModal()
    await flushPromises()
    await chooseMode(wrapper, 'HUNT')
    await flushPromises()

    expect(storeMock.fetchCreatures).toHaveBeenCalledWith('vault-1', 'test-token')
    expect(wrapper.findAll('.team-label').map((label) => label.text())).toEqual([
      'TEAM A',
      'CREATURES',
    ])
    expect(slots(wrapper)).toHaveLength(2)
    expect(wrapper.findAll('.creature-slot')).toHaveLength(1)
    expect(wrapper.text()).toContain('+ ADD CREATURE')
    expect(storeMock.setFighters).not.toHaveBeenCalled()
  })

  it('persists the hunt payload with dweller slots and opponent keys', async () => {
    const wrapper = mountModal()
    await flushPromises()
    await chooseMode(wrapper, 'HUNT')
    await flushPromises()

    const secondDweller = await openPicker(wrapper, 1)
    await pickOption(secondDweller, 'Charlie Dweller')
    expect(storeMock.setFighters).not.toHaveBeenCalled()

    const creature = wrapper.get('.creature-slot')
    await creature.get('.creature-slot-empty').trigger('click')
    await flushPromises()
    await pickOption(creature, 'Radroach swarm')

    expect(storeMock.setFighters).toHaveBeenCalledTimes(1)
    expect(storeMock.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      {
        mode: 'hunt',
        fighterAId: 'a-1',
        fighterBId: null,
        fighterCId: 'c-1',
        fighterDId: null,
        teamABotKey: null,
        teamBBotKey: null,
        opponentKeys: ['radroach-swarm'],
      },
      'test-token'
    )
  })

  it.each([
    ['Pest Control', ['radroach-swarm', 'bloatfly'], 45],
    ['Wasteland Pack', ['mole-rat-pack', 'night-stalker'], 50],
    ['Heavyweights', ['mirelurk', 'yao-guai'], 80],
  ] as const)('selects %s through the existing hunt draft', async (name, keys, power) => {
    roomState.value = storeMock.huntRoom
    const wrapper = mountModal()
    await flushPromises()
    const group = wrapper.get('[aria-label="Hunt preset"]')
    await group
      .findAll('button')
      .find((button) => button.text() === name)!
      .trigger('click')
    await flushPromises()
    expect(storeMock.setFighters).toHaveBeenCalledTimes(1)
    expect(storeMock.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      expect.objectContaining({ mode: 'hunt', fighterAId: 'a-1', opponentKeys: [...keys] }),
      'test-token'
    )
    expect(wrapper.text()).toContain(`Combined opponent power: ${power}`)
    expect(
      group
        .findAll('button')
        .find((button) => button.text() === name)!
        .attributes('aria-pressed')
    ).toBe('true')
  })

  it('allows customizing a preset and clears its selected state', async () => {
    roomState.value = storeMock.huntRoom
    const wrapper = mountModal()
    await flushPromises()
    const group = wrapper.get('[aria-label="Hunt preset"]')
    await group
      .findAll('button')
      .find((button) => button.text() === 'Heavyweights')!
      .trigger('click')
    await flushPromises()
    await wrapper.get('button[aria-label="Clear Mirelurk"]').trigger('click')
    await flushPromises()
    expect(storeMock.setFighters).toHaveBeenLastCalledWith(
      'vault-1',
      'room-1',
      expect.objectContaining({ opponentKeys: ['yao-guai'] }),
      'test-token'
    )
    expect(group.findAll('[aria-pressed="true"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('Combined opponent power: 40')
  })

  it('locks hunt presets during a fight and hides them in other modes', async () => {
    let wrapper = mountModal()
    await flushPromises()
    expect(wrapper.find('[aria-label="Hunt preset"]').exists()).toBe(false)
    wrapper.unmount()
    roomState.value = { ...storeMock.huntRoom, fight_started: true, match_done: false }
    wrapper = mountModal()
    await flushPromises()
    expect(wrapper.find('[aria-label="Hunt preset"]').exists()).toBe(false)
    expect(wrapper.find('.teams-row').exists()).toBe(false)
    expect(storeMock.setFighters).not.toHaveBeenCalled()
  })

  it('renders hunted creatures on team B with matching artwork and live stats', async () => {
    roomState.value = storeMock.huntRoom
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.findAll('.team-label').map((label) => label.text())).toEqual([
      'TEAM A',
      'CREATURES',
    ])
    const creature = wrapper.get('.creature-slot')
    expect(creature.text()).toContain('Radroach swarm')
    expect(creature.text()).toContain('POW 35')
    expect(creature.text()).toContain('35/35')
    expect(creature.get('img').attributes('src')).toContain(
      '/static/creature_images/assembled/radroach.webp'
    )
    expect(creature.get('img').attributes('alt')).toBe('Radroach swarm')
    expect(creature.find('.fighter-portrait').exists()).toBe(false)
    expect(wrapper.text()).toContain('READY')
    expect(wrapper.text()).toContain('START FIGHT')
  })

  it('labels hunt readiness with dwellers plus creatures', async () => {
    roomState.value = { ...storeMock.huntRoom, can_start: false }
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('NEEDS DWELLERS + CREATURES')
  })

  it.each([true, false])(
    'refreshes vault stock and stops on a failed heal (success=%s)',
    async (success) => {
      roomState.value = {
        ...storeMock.readyRoom,
        match_done: true,
        team_a: storeMock.readyRoom.team_a.map((fighter) => ({ ...fighter, health: 10 })),
        team_b: storeMock.readyRoom.team_b.map((fighter) => ({ ...fighter, health: 10 })),
      }
      const wrapper = mountModal()
      const medical = useDwellerMedicalStore()
      const heal = vi
        .spyOn(medical, 'useStimpack')
        .mockResolvedValue(success ? ({ health: 60 } as never) : null)
      const refresh = vi.spyOn(useVaultStore(), 'refreshVault').mockResolvedValue()
      await flushPromises()
      await wrapper
        .findAll('button')
        .find((button) => button.text().includes('HEAL INJURED'))!
        .trigger('click')
      await flushPromises()
      expect(heal).toHaveBeenCalledTimes(success ? 2 : 1)
      expect(heal).toHaveBeenCalledWith('a-1', 'test-token')
      expect(refresh).toHaveBeenCalledWith('vault-1', 'test-token')
    }
  )

  it('excludes defeated creatures from the heal-injured action', async () => {
    roomState.value = {
      ...storeMock.huntRoom,
      match_done: true,
      winner_name: 'Alpha Dweller',
      team_a: storeMock.huntRoom.team_a.map((fighter) => ({ ...fighter, health: 20 })),
      team_b: storeMock.huntRoom.team_b.map((fighter) => ({ ...fighter, health: 0 })),
    }
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('HEAL INJURED (1)')
  })

  it('keeps room-management actions out of the battle panel', async () => {
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.find('.arena-management').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Unassign All Dwellers')
    expect(wrapper.text()).not.toContain('Destroy Room')
  })

  it('shows a retry state when loading the arena fails', async () => {
    controller.loadFailed.value = true
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Unable to load Arena status.')
    await wrapper.get('button').trigger('click')
    expect(controller.retry).toHaveBeenCalledTimes(1)
    controller.loadFailed.value = false
  })

  it('shows the winner banner when a match is done', async () => {
    roomState.value = {
      ...storeMock.readyRoom,
      match_done: true,
      winner_name: 'Alpha Dweller',
    }
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('MATCH COMPLETE')
    expect(wrapper.text()).toContain('Alpha Dweller wins')
  })

  it('shows the server-awarded XP in the completed match result', async () => {
    const reward = 'Alpha +120 XP, Charlie +120 XP, Alpha & Charlie happiness +10'
    roomState.value = {
      ...storeMock.huntRoom,
      match_done: true,
      winner_name: 'Alpha Dweller & Charlie Dweller',
      events: [
        { id: 'old-reward', round_seq: 1, kind: 'reward', message: 'Old fighter +60 XP' },
        { id: 'finish', round_seq: 2, kind: 'finish', message: 'Dwellers defeated Creatures!' },
        { id: 'reward', round_seq: 2, kind: 'reward', message: reward },
      ],
    }
    const wrapper = mountModal()
    await flushPromises()
    const banner = wrapper.get('.result-banner')
    expect(banner.text()).toContain(reward)
    expect(banner.text()).not.toContain('Old fighter')
  })

  it('does not show an older reward beside a new legacy result', async () => {
    roomState.value = {
      ...storeMock.huntRoom,
      match_done: true,
      winner_name: 'Alpha Dweller',
      events: [
        { id: 'old-reward', round_seq: 1, kind: 'reward', message: 'Old fighter +60 XP' },
        { id: 'finish', round_seq: 2, kind: 'finish', message: 'Dwellers defeated Creatures!' },
      ],
    }
    const wrapper = mountModal()
    await flushPromises()
    expect(wrapper.get('.result-banner').text()).not.toContain('Old fighter')
  })

  it.each(['hunt', 'brawl'])('credits the complete winning side in %s mode', async (mode) => {
    roomState.value = {
      ...storeMock.readyRoom,
      mode,
      match_done: true,
      winner_name: 'Alpha Dweller & Charlie Dweller',
    }
    const wrapper = mountModal()
    await flushPromises()
    expect(wrapper.get('.result-banner').text()).toBe(
      'MATCH COMPLETE — Victory for Alpha Dweller & Charlie Dweller!'
    )
  })

  it('renders legacy journal entries in order without round labels', async () => {
    roomState.value = {
      ...storeMock.readyRoom,
      events: [
        {
          id: 'e4',
          round_seq: 4,
          kind: 'finish',
          message: 'Alpha Dweller defeated Bravo Dweller!',
        },
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
    expect(items[0].text()).not.toContain('R1')
    expect(items[1].text()).toContain('Alpha Dweller hits Bravo Dweller for 5')
    expect(items[1].text()).not.toContain('R2')
    expect(items[1].text()).toContain('×2')
    expect(items[2].text()).toContain('FINISH')
    expect(items[2].text()).not.toContain('R4')
  })

  it('orders timestamped events by real time without collapsing separate hits', async () => {
    roomState.value = {
      ...storeMock.readyRoom,
      events: [
        {
          id: 'last',
          round_seq: 1,
          kind: 'skill',
          message: 'Alpha uses Aimed Shot on Bravo for 2',
          created_at: '2026-10-18T12:00:03+00:00',
        },
        {
          id: 'middle',
          round_seq: 99,
          kind: 'hit',
          message: 'Alpha hits Bravo for 1',
          created_at: '2026-10-18T12:00:02+00:00',
        },
        {
          id: 'first',
          round_seq: 100,
          kind: 'hit',
          message: 'Alpha hits Bravo for 1',
          created_at: '2026-10-18T12:00:01+00:00',
        },
      ],
    }
    const wrapper = mountModal()
    await flushPromises()
    const entries = wrapper.findAll('[aria-label="Battle log"] li')
    expect(entries).toHaveLength(3)
    expect(entries.map((entry) => entry.get('time').attributes('datetime'))).toEqual([
      '2026-10-18T12:00:01+00:00',
      '2026-10-18T12:00:02+00:00',
      '2026-10-18T12:00:03+00:00',
    ])
    expect(entries.every((entry) => /^\d{2}:\d{2}:\d{2}$/.test(entry.get('time').text()))).toBe(
      true
    )
    expect(entries[2].find('svg').exists()).toBe(true)
    expect(entries[2].text()).toContain('SKILL')
    expect(wrapper.get('[aria-label="Battle log"]').text()).not.toContain('×2')
  })

  it('shows a polite empty state when no rounds have been fought', async () => {
    const wrapper = mountModal()
    await flushPromises()

    const journal = wrapper.get('[aria-label="Battle log"]')
    expect(journal.attributes('aria-live')).toBe('polite')
    expect(journal.text()).toContain('No attacks yet.')
  })

  it('resyncs the draft when the server rejects a selection', async () => {
    storeMock.setFighters.mockResolvedValueOnce(false)
    const wrapper = mountModal()
    await flushPromises()
    expect(wrapper.text()).toContain('START FIGHT')

    const slot = slots(wrapper)[0]
    const swap = slot.get('button[aria-label^="Swap"]')
    await swap.trigger('click')
    await flushPromises()
    await pickOption(slot, 'Charlie Dweller')

    expect(storeMock.setFighters).toHaveBeenCalledTimes(1)
    expect(slots(wrapper)[0].text()).toContain('Alpha Dweller')
    expect(wrapper.text()).toContain('START FIGHT')
    expect(wrapper.text()).toContain('READY')
    expect(wrapper.text()).not.toContain('NEEDS 2 FIGHTERS')
  })
  it.each(['hunt', 'brawl'] as const)('never offers a Team A bot in %s', async (mode) => {
    roomState.value = { ...storeMock.huntRoom, mode }
    const wrapper = mountModal()
    await flushPromises()
    expect(wrapper.find('[aria-label="Team A partner"]').exists()).toBe(false)
    if (mode === 'brawl') expect(wrapper.find('[aria-label="Team B partner"]').exists()).toBe(true)
  })

  it('preserves a Team B bot draft across polling and commits it with two Team A dwellers', async () => {
    const wrapper = mountModal()
    await flushPromises()
    await chooseMode(wrapper, 'BRAWL')
    await pickOption(await openPicker(wrapper, 1), 'Charlie Dweller')
    const group = wrapper.get('[aria-label="Team B partner"]')
    await group
      .findAll('button')
      .find((b) => b.text() === 'Bot')!
      .trigger('click')
    await flushPromises()
    roomState.value = { ...roomState.value! }
    await flushPromises()
    expect(
      group
        .findAll('button')
        .find((b) => b.text() === 'Bot')!
        .attributes('aria-pressed')
    ).toBe('true')
    expect(wrapper.findAll('.picker-option').some((b) => b.text().includes('Deathclaw'))).toBe(
      false
    )
    await wrapper
      .findAll('.picker-option')
      .find((b) => b.text().includes('Training Eyebot'))!
      .trigger('click')
    await flushPromises()
    expect(storeMock.setFighters).toHaveBeenLastCalledWith(
      'vault-1',
      'room-1',
      expect.objectContaining({
        mode: 'brawl',
        fighterAId: 'a-1',
        fighterCId: 'c-1',
        fighterBId: 'b-1',
        teamABotKey: null,
        teamBBotKey: 'training-eyebot',
      }),
      'test-token'
    )
    expect(wrapper.text()).toContain('Team B training bots reset each match and earn no rewards.')
  })
})
