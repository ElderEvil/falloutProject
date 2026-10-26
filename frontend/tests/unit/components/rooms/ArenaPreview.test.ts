import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { computed, defineComponent, h, ref } from 'vue'
import ArenaPreview from '@/modules/rooms/components/ArenaPreview.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import {
  useArenaMatchDraft,
  type ArenaMatchDraft,
} from '@/modules/rooms/composables/useArenaMatchDraft'
import type { ArenaRoomController } from '@/modules/rooms/composables/useArenaRoom'
import type {
  ArenaCreature,
  ArenaFighter,
  ArenaRosterEntry,
  ArenaRoomState,
} from '@/modules/rooms/api/arena'

vi.mock('@iconify/vue', () => ({
  Icon: { props: ['icon'], template: '<span :data-icon="icon" />' },
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    management: { unassignDwellerFromRoom: vi.fn() },
  }),
}))

vi.mock('@/modules/dwellers/stores/dwellerMedical', () => ({
  useDwellerMedicalStore: () => ({ useStimpack: vi.fn() }),
}))

vi.mock('@/modules/vault/stores/vault', () => ({
  useVaultStore: () => ({ refreshVault: vi.fn() }),
}))

const arenaStoreMock = vi.hoisted(() => ({
  fetchCreatures: vi.fn(),
  setFighters: vi.fn(),
  clearEvents: vi.fn(),
  creatures: [] as ArenaCreature[],
}))

vi.mock('@/modules/rooms/stores/arena', () => ({
  useArenaStore: () => arenaStoreMock,
}))

const fighter = (id: string, overrides: Partial<ArenaFighter> = {}): ArenaFighter => ({
  id,
  name: id,
  level: 5,
  health: 80,
  max_health: 100,
  power: 10,
  is_creature: false,
  is_robot: false,
  active_skill: {
    name: 'Aimed Shot',
    icon: 'gun-rifle',
    description: 'Extra attack on your next team turn.',
    charge: 100,
    queued: false,
  },
  ...overrides,
})

const rosterEntry = (id: string, name = id): ArenaRosterEntry => ({
  id,
  name,
  level: 5,
  health: 80,
  max_health: 100,
})

const state = (overrides: Partial<ArenaRoomState> = {}): ArenaRoomState => ({
  room_id: 'arena',
  room_name: 'Arena',
  tier: 3,
  available_modes: ['duel', 'brawl', 'training', 'hunt'],
  mode: 'duel',
  next_attack_team: 'A',
  fighter_a_id: 'a',
  fighter_b_id: 'b',
  fighters: [fighter('a'), fighter('b')],
  team_a: [fighter('a')],
  team_b: [fighter('b')],
  roster: [],
  fight_ready: true,
  can_start: true,
  fight_started: false,
  match_done: false,
  countdown_remaining: 0,
  winner_name: null,
  events: [],
  ...overrides,
})

const stateRef = ref<ArenaRoomState | null>(null)

const controller: ArenaRoomController = {
  roomState: computed(() => stateRef.value),
  isLoading: ref(false),
  loadFailed: ref(false),
  pendingSkills: ref(new Set<string>()),
  damageNumbers: ref<Array<{ id: number; fighterId: string; amount: number }>>([]),
  attackingTeam: ref<'A' | 'B' | null>(null),
  attackingFighterId: ref<string | null>(null),
  skillBurst: ref<{ id: string; message: string } | null>(null),
  load: vi.fn().mockResolvedValue(undefined),
  retry: vi.fn().mockResolvedValue(undefined),
  refresh: vi.fn().mockResolvedValue(undefined),
  queueSkill: vi.fn().mockResolvedValue(undefined),
  startFight: vi.fn().mockResolvedValue(true),
  stopFight: vi.fn().mockResolvedValue(true),
  resetDamageTracking: vi.fn(),
}

let currentMatch: ArenaMatchDraft
const emitted: Array<{ event: string; args: unknown[] }> = []

const Host = defineComponent({
  setup() {
    currentMatch = useArenaMatchDraft('vault-1', 'room-1', controller)
    return () =>
      h(ArenaPreview, {
        match: currentMatch,
        onSkill: (id: string) => emitted.push({ event: 'skill', args: [id] }),
        onStop: () => emitted.push({ event: 'stop', args: [] }),
        onAssignDwellers: () => emitted.push({ event: 'assignDwellers', args: [] }),
      })
  },
})

const mountPreview = async (initial: ArenaRoomState) => {
  stateRef.value = initial
  const wrapper = mount(Host)
  await flushPromises()
  return wrapper
}

describe('ArenaPreview', () => {
  beforeEach(() => {
    emitted.length = 0
    stateRef.value = null
    arenaStoreMock.fetchCreatures.mockReset().mockResolvedValue(true)
    arenaStoreMock.setFighters.mockReset().mockResolvedValue(true)
    arenaStoreMock.clearEvents.mockReset().mockResolvedValue(true)
    arenaStoreMock.creatures = [
      { key: 'training-eyebot', name: 'Training Eyebot', power: 30, max_hp: 20, is_robot: true },
      { key: 'radroach-swarm', name: 'Radroach swarm', power: 35, max_hp: 35 },
      { key: 'deathclaw', name: 'Deathclaw', power: 120, max_hp: 120 },
      { key: 'bloatfly', name: 'Bloatfly', power: 10, max_hp: 10 },
    ]
    controller.startFight.mockReset().mockResolvedValue(true)
    controller.stopFight.mockClear()
  })

  it('renders both teams and their meters in setup', async () => {
    const wrapper = await mountPreview(state())

    expect(wrapper.find('.arena-preview').exists()).toBe(true)
    expect(wrapper.find('.arena-ring').exists()).toBe(false)
    expect(wrapper.text()).toContain('TEAM A')
    expect(wrapper.text()).toContain('TEAM B')
    expect(wrapper.findAll('.combatant-meters')).toHaveLength(2)
    expect(wrapper.get('[aria-label="Arena preview"]').text()).toContain('a')
    expect(wrapper.get('[aria-label="Arena preview"]').text()).toContain('b')
  })

  it('keeps an equipped pet visible from arena setup through the fight', async () => {
    const alpha = fighter('a', {
      pet: { name: 'CX404', image_url: '/static/pet_images/FOS CX404.png' },
    })
    const beta = fighter('b')
    const initial = state({ fighters: [alpha, beta], team_a: [alpha], team_b: [beta] })
    const wrapper = await mountPreview(initial)
    expect(wrapper.get('.arena-preview img[alt="CX404, a’s pet"]').exists()).toBe(true)
    stateRef.value = { ...initial, fight_started: true }
    await flushPromises()
    expect(wrapper.get('.arena-ring img[alt="CX404, a’s pet"]').exists()).toBe(true)
    expect(wrapper.findAll('.fighter-meters')).toHaveLength(2)
    wrapper.unmount()
  })

  it.each(['duel', 'brawl'] as const)('hides Hunt presets in %s', async (mode) => {
    const wrapper = await mountPreview(
      state({
        mode,
        roster: ['a', 'b', 'c', 'd'].map((id) => rosterEntry(id)),
      })
    )
    expect(wrapper.find('[aria-label="Hunt preset"]').exists()).toBe(false)
  })

  it('offers Start fight directly while setup remains a local draft', async () => {
    const wrapper = await mountPreview(state())
    expect(
      wrapper
        .findAll('button')
        .find((button) => button.text() === 'START FIGHT')!
        .attributes('disabled')
    ).toBeUndefined()
    expect(controller.startFight).not.toHaveBeenCalled()
    expect(arenaStoreMock.setFighters).not.toHaveBeenCalled()
  })

  it('retains a local lineup when starting is rejected', async () => {
    await mountPreview(state({ roster: ['a', 'b', 'c'].map((id) => rosterEntry(id)) }))
    controller.startFight.mockResolvedValueOnce(false)
    currentMatch.selectFighter('a', rosterEntry('c'))
    await currentMatch.startFight()
    expect(currentMatch.draft.a).toBe('c')
    expect(currentMatch.draft.b).toBe('b')
    expect(currentMatch.isStarting).toBe(false)
  })

  it('keeps an incomplete bot draft through polling and prevents starting it', async () => {
    const initial = state({
      roster: ['a', 'b', 'c'].map((id) => rosterEntry(id)),
      team_a: [fighter('a'), fighter('c')],
    })
    const wrapper = await mountPreview(initial)
    currentMatch.selectMode('training')
    currentMatch.toggleCreaturePicker(0)
    currentMatch.selectCreature(
      arenaStoreMock.creatures.find((entry) => entry.key === 'training-eyebot')!
    )
    stateRef.value = { ...initial }
    await flushPromises()
    expect(currentMatch.mode).toBe('training')
    expect(currentMatch.opponentKeys).toEqual(['training-eyebot'])
    expect(currentMatch.canStart).toBe(false)
    expect(
      wrapper
        .findAll('button')
        .find((button) => button.text() === 'START FIGHT')!
        .attributes('disabled')
    ).toBeDefined()
    expect(arenaStoreMock.setFighters).not.toHaveBeenCalled()
  })

  it('places recovery next to the rematch action and heals through the match draft', async () => {
    const wrapper = await mountPreview(
      state({
        match_done: true,
        team_a: [fighter('a', { health: 10 })],
        team_b: [fighter('b', { health: 10 })],
      })
    )
    const heal = vi.spyOn(currentMatch, 'healInjured').mockResolvedValue(undefined)
    const controls = wrapper.get('.result-banner').findAll('button')
    expect(controls.map((button) => button.text())).toEqual([
      'FIGHT AGAIN',
      'HEAL INJURED (2)',
      'CHANGE FIGHTERS',
    ])
    await controls[1].trigger('click')
    expect(heal).toHaveBeenCalledOnce()
    currentMatch.isHealing = true
    await flushPromises()
    expect(controls[1].attributes('disabled')).toBeDefined()
  })

  it.each([true, false])(
    'only shows rewards belonging to the latest result (reward=%s)',
    async (hasReward) => {
      const wrapper = await mountPreview(
        state({
          match_done: true,
          events: [
            { id: 'old', round_seq: 1, kind: 'reward', message: 'Old fighter +60 XP' },
            { id: 'finish', round_seq: 2, kind: 'finish', message: 'Match complete' },
            ...(hasReward
              ? [{ id: 'reward', round_seq: 2, kind: 'reward', message: 'Alpha +120 XP' }]
              : []),
          ],
        })
      )
      const banner = wrapper.get('.result-banner').text()
      expect(banner).not.toContain('Old fighter')
      expect(banner.includes('Alpha +120 XP')).toBe(hasReward)
    }
  )

  it('shows two empty creature slots for an empty Hunt lineup', async () => {
    const wrapper = await mountPreview(
      state({
        mode: 'hunt',
        fighter_a_id: null,
        fighter_b_id: null,
        team_a: [],
        team_b: [],
        fighters: [],
      })
    )
    currentMatch.setStage('fighters')
    await flushPromises()
    const labels = wrapper.findAll('button').map((button) => button.attributes('aria-label'))
    expect(labels).toContain('Select creature 1 for Team B')
    expect(labels).toContain('Select creature 2 for Team B')
  })

  it('maps arena dwellers to body-size classes', async () => {
    const teen = fighter('a', { age_group: 'teen', race: 'human' })
    const mutant = fighter('b', { age_group: 'adult', race: 'super_mutant' })
    const wrapper = await mountPreview(state({ team_a: [teen], team_b: [mutant] }))
    const exposed = wrapper.findComponent(ArenaPreview).vm as unknown as {
      bodySizeFor: (fighter: ArenaFighter) => string
    }

    expect(exposed.bodySizeFor(teen)).toBe('small')
    expect(exposed.bodySizeFor(mutant)).toBe('large')
  })

  it('does not apply the curated portrait zoom in the arena', async () => {
    const curated = fighter('a', { image_url: '/static/dweller_images/test.png' })
    const wrapper = await mountPreview(state({ team_a: [curated], team_b: [] }))

    expect(wrapper.findComponent(DwellerPortrait).props('zoom')).toBe(false)
  })

  it('shows silhouette slots for empty team positions', async () => {
    const wrapper = await mountPreview(
      state({
        team_a: [],
        team_b: [],
        fighter_a_id: null,
        fighter_b_id: null,
        fighters: [],
      })
    )

    expect(wrapper.findAll('.arena-empty-slot')).toHaveLength(2)
    expect(wrapper.findAll('.arena-dweller-silhouette')).toHaveLength(2)
  })

  it('switches to the ring once the fight starts', async () => {
    const wrapper = await mountPreview(state({ fight_started: true }))

    expect(wrapper.find('.arena-ring').exists()).toBe(true)
    expect(wrapper.find('.arena-preview').exists()).toBe(false)
    expect(wrapper.findAll('.fighter-meters')).toHaveLength(2)
  })

  it('keeps setup actions read-only', async () => {
    const wrapper = await mountPreview(state())

    expect(
      wrapper.get('button[aria-label^="Use Aimed Shot for a"]').attributes('disabled')
    ).toBeDefined()
  })

  it('passes fighter skill activation through during the fight', async () => {
    const wrapper = await mountPreview(state({ fight_started: true }))
    expect(
      wrapper
        .get('button[aria-label^="Use Aimed Shot for a"] [data-skill-icon]')
        .attributes('data-skill-icon')
    ).toBe('gun-rifle')

    await wrapper.get('button[aria-label^="Use Aimed Shot for a"]').trigger('click')

    expect(emitted).toContainEqual({ event: 'skill', args: ['a'] })
  })

  it('switches the shared stage to four dweller slots for Team fight', async () => {
    const wrapper = await mountPreview(state())
    const modes = wrapper.get('nav[aria-label="Match mode"]').findAll('button')
    expect(modes).toHaveLength(4)
    await modes.find((button) => button.text().includes('Team fight'))!.trigger('click')
    expect(currentMatch.mode).toBe('brawl')
    expect(wrapper.findAll('button[aria-label^="Select fighter"]')).toHaveLength(4)
  })

  it('disables modes the server has not unlocked', async () => {
    const wrapper = await mountPreview(state({ available_modes: ['duel'] }))
    const modes = wrapper.get('nav[aria-label="Match mode"]').findAll('button')
    expect(modes[0].attributes('disabled')).toBeUndefined()
    for (const button of modes.slice(1)) expect(button.attributes('disabled')).toBeDefined()
  })

  it('starts the match directly from the shared setup', async () => {
    const wrapper = await mountPreview(state())
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'START FIGHT')!
      .trigger('click')
    await flushPromises()
    expect(controller.startFight).toHaveBeenCalledWith(
      expect.objectContaining({ mode: 'duel', fighterAId: 'a', fighterBId: 'b' })
    )
    expect(currentMatch.stage).toBe('fight')
  })

  it('submits all four dweller slots together when Team fight starts', async () => {
    const charlie = rosterEntry('c'),
      delta = rosterEntry('d')
    const wrapper = await mountPreview(
      state({ roster: [rosterEntry('a'), rosterEntry('b'), charlie, delta] })
    )
    currentMatch.selectMode('brawl')
    currentMatch.selectFighter('c', charlie)
    currentMatch.selectFighter('d', delta)
    expect(arenaStoreMock.setFighters).not.toHaveBeenCalled()
    await flushPromises()
    expect(wrapper.findAll('button[aria-label^="Select fighter"]')).toHaveLength(4)
    await currentMatch.startFight()
    expect(controller.startFight).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'brawl',
        fighterAId: 'a',
        fighterBId: 'b',
        fighterCId: 'c',
        fighterDId: 'd',
      })
    )
  })

  it('keeps two creature positions stable and submits both opponents at start', async () => {
    await mountPreview(
      state({ mode: 'hunt', fighter_b_id: null, team_a: [fighter('a'), fighter('c')], team_b: [] })
    )
    currentMatch.toggleCreaturePicker(1)
    currentMatch.selectCreature(arenaStoreMock.creatures.find((entry) => entry.key === 'bloatfly')!)
    expect(currentMatch.teamB[0]).toBeNull()
    expect(currentMatch.teamB[1]?.name).toBe('Bloatfly')
    currentMatch.toggleCreaturePicker(0)
    currentMatch.selectCreature(
      arenaStoreMock.creatures.find((entry) => entry.key === 'deathclaw')!
    )
    currentMatch.clearCreature('deathclaw')
    expect(currentMatch.teamB[0]).toBeNull()
    expect(currentMatch.teamB[1]?.name).toBe('Bloatfly')
    currentMatch.toggleCreaturePicker(0)
    currentMatch.selectCreature(
      arenaStoreMock.creatures.find((entry) => entry.key === 'deathclaw')!
    )
    await currentMatch.startFight()
    expect(controller.startFight).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'hunt',
        fighterBId: null,
        opponentKeys: ['deathclaw', 'bloatfly'],
      })
    )
  })

  it('offers only robots for Bot training and starts a full two-bot team', async () => {
    arenaStoreMock.creatures.push({
      key: 'training-protectron',
      name: 'Training Protectron',
      power: 10,
      max_hp: 60,
      is_robot: true,
    })
    const wrapper = await mountPreview(
      state({
        mode: 'training',
        fighter_b_id: null,
        team_a: [fighter('a'), fighter('c')],
        team_b: [],
      })
    )
    expect(currentMatch.creaturePickerOptions.every((entry) => entry.is_robot)).toBe(true)
    for (const [index, key] of ['training-eyebot', 'training-protectron'].entries()) {
      currentMatch.toggleCreaturePicker(index)
      currentMatch.selectCreature(arenaStoreMock.creatures.find((entry) => entry.key === key)!)
    }
    await flushPromises()
    expect(wrapper.findAll('button[aria-label^="Select bot"]')).toHaveLength(2)
    await currentMatch.startFight()
    expect(controller.startFight).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'training',
        fighterBId: null,
        fighterCId: 'c',
        opponentKeys: ['training-eyebot', 'training-protectron'],
      })
    )
  })

  it('allows a rematch using the actual health of a knocked-out dweller', async () => {
    await mountPreview(
      state({
        match_done: true,
        team_b: [fighter('b', { health: 0 })],
        candidates: [rosterEntry('a'), { ...rosterEntry('b'), health: 1 }],
      })
    )
    await currentMatch.rematch()
    expect(controller.startFight).toHaveBeenCalledWith(expect.objectContaining({ fighterBId: 'b' }))
  })

  it('shows the skill icon and uncharged meter for a newly picked Team B dweller', async () => {
    const candidate = {
      ...rosterEntry('new'),
      active_skill: { ...fighter('new').active_skill!, charge: 0 },
    }
    const wrapper = await mountPreview(
      state({ team_b: [], fighter_b_id: null, candidates: [candidate] })
    )
    currentMatch.selectFighter('b', candidate)
    await flushPromises()
    const skill = wrapper.get('button[aria-label="Use Aimed Shot for new, 0% charged"]')
    expect(skill.get('[data-skill-icon]').attributes('data-skill-icon')).toBe('gun-rifle')
    expect(skill.attributes('disabled')).toBeDefined()
  })

  it('selects a vault adult outside the Arena without an assignment request during setup', async () => {
    const candidate = {
      ...rosterEntry('new', 'Lucy'),
      room_id: 'generator',
      room_name: 'Power Generator',
    }
    const wrapper = await mountPreview(state({ candidates: [candidate], roster: [] }))
    await wrapper.get('button[aria-label="Select fighter 1 for Team A"]').trigger('click')
    expect(wrapper.get('[aria-label="Choose fighter"]').text()).toContain('Power Generator → Arena')
    await wrapper.get('.picker-option').trigger('click')
    expect(currentMatch.draft.a).toBe('new')
    expect(arenaStoreMock.setFighters).not.toHaveBeenCalled()
    await currentMatch.startFight()
    expect(controller.startFight).toHaveBeenCalledWith(
      expect.objectContaining({ fighterAId: 'new' })
    )
  })
})
