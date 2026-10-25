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
  available_modes: ['duel', 'brawl', 'hunt'],
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

const stageButton = (wrapper: ReturnType<typeof mount>, label: string) =>
  wrapper
    .get('nav[aria-label="Arena stages"]')
    .findAll('button')
    .find(
      (button) =>
        button
          .text()
          .replace(/^\d+\s*/, '')
          .trim() === label
    )!

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
    controller.startFight.mockClear()
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

  it.each(['duel', 'brawl'] as const)('hides Hunt presets in %s', async (mode) => {
    const wrapper = await mountPreview(
      state({
        mode,
        roster: ['a', 'b', 'c', 'd'].map((id) => rosterEntry(id)),
      })
    )
    expect(wrapper.find('[aria-label="Hunt preset"]').exists()).toBe(false)
  })

  it('offers a clear next step after choosing fighters without starting a match', async () => {
    const wrapper = await mountPreview(state())
    const review = wrapper.findAll('button').find((button) => button.text() === 'Review fight')!
    expect(review).toBeDefined()
    await review.trigger('click')
    expect(currentMatch.stage).toBe('fight')
    expect(controller.startFight).not.toHaveBeenCalled()
  })

  it('restores the server selection when a fighter change is rejected', async () => {
    await mountPreview(state({ roster: ['a', 'b', 'c'].map((id) => rosterEntry(id)) }))
    arenaStoreMock.setFighters.mockResolvedValueOnce(false)
    currentMatch.selectFighter('a', rosterEntry('c'))
    await flushPromises()
    expect(currentMatch.draft.a).toBe('a')
    expect(currentMatch.draft.b).toBe('b')
  })

  it('keeps an incomplete bot draft through polling and prevents starting it', async () => {
    const initial = state({
      mode: 'brawl',
      roster: ['a', 'b', 'c', 'd'].map((id) => rosterEntry(id)),
      team_a: [fighter('a'), fighter('c')],
      team_b: [fighter('b'), fighter('d')],
    })
    const wrapper = await mountPreview(initial)
    currentMatch.choosePartnerType('B', true)
    stateRef.value = { ...initial }
    await flushPromises()
    expect(currentMatch.botEnabled.B).toBe(true)
    expect(currentMatch.botKeys.B).toBeNull()
    expect(currentMatch.canStart).toBe(false)
    expect(
      wrapper
        .findAll('button')
        .find((button) => button.text() === 'Review fight')!
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
    await stageButton(wrapper, 'Fighters').trigger('click')

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

  it('drives the mode stage and switches to brawl slots', async () => {
    const wrapper = await mountPreview(state())

    await stageButton(wrapper, 'Mode').trigger('click')
    expect(wrapper.findAll('.mode-option')).toHaveLength(3)
    expect(wrapper.findAll('.mode-option')[0].attributes('aria-pressed')).toBe('true')

    const brawl = wrapper.findAll('.mode-option').find((option) => option.text().includes('Brawl'))!
    await brawl.trigger('click')
    await flushPromises()

    expect(currentMatch.mode).toBe('brawl')
    expect(currentMatch.stage).toBe('fighters')
    expect(wrapper.findAll('.fighter-slot')).toHaveLength(4)
  })

  it('disables modes the server has not unlocked', async () => {
    const wrapper = await mountPreview(state({ available_modes: ['duel'] }))

    await stageButton(wrapper, 'Mode').trigger('click')
    const brawl = wrapper.findAll('.mode-option').find((option) => option.text().includes('Brawl'))!
    const hunt = wrapper.findAll('.mode-option').find((option) => option.text().includes('Hunt'))!

    expect(brawl.attributes('disabled')).toBeDefined()
    expect(hunt.attributes('disabled')).toBeDefined()
  })

  it('starts the fight from the fight stage', async () => {
    const wrapper = await mountPreview(state())

    await stageButton(wrapper, 'Fight').trigger('click')
    const start = wrapper.findAll('button').find((button) => button.text().includes('START FIGHT'))!
    await start.trigger('click')
    await flushPromises()

    expect(controller.startFight).toHaveBeenCalledTimes(1)
    expect(currentMatch.stage).toBe('fight')
  })

  it('persists a complete brawl selection', async () => {
    const charlie = rosterEntry('c', 'Charlie Dweller')
    const delta = rosterEntry('d', 'Delta Dweller')
    const wrapper = await mountPreview(
      state({ roster: [rosterEntry('a', 'Alpha'), rosterEntry('b', 'Bravo'), charlie, delta] })
    )

    currentMatch.selectMode('brawl')
    await flushPromises()
    currentMatch.selectFighter('c', charlie)
    currentMatch.selectFighter('d', delta)
    await flushPromises()

    expect(arenaStoreMock.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      {
        mode: 'brawl',
        fighterAId: 'a',
        fighterBId: 'b',
        fighterCId: 'c',
        fighterDId: 'd',
        teamABotKey: null,
        teamBBotKey: null,
      },
      'test-token'
    )
    expect(wrapper.findAll('.fighter-slot')).toHaveLength(4)
  })

  it('persists a hunt creature selection', async () => {
    const radroach = fighter('radroach-swarm#0', {
      name: 'Radroach swarm',
      is_creature: true,
      power: 35,
    })
    const wrapper = await mountPreview(
      state({
        mode: 'hunt',
        fighter_b_id: null,
        fighters: [fighter('a'), radroach],
        team_b: [radroach],
      })
    )

    currentMatch.clearCreature('radroach-swarm')
    await flushPromises()
    currentMatch.selectCreature(arenaStoreMock.creatures.find((c) => c.key === 'deathclaw')!)
    await flushPromises()

    expect(arenaStoreMock.setFighters).toHaveBeenLastCalledWith(
      'vault-1',
      'room-1',
      expect.objectContaining({
        mode: 'hunt',
        fighterAId: 'a',
        fighterBId: null,
        opponentKeys: ['deathclaw'],
      }),
      'test-token'
    )
    expect(wrapper.findAll('.creature-slot')).toHaveLength(2)
  })

  it('persists a brawl training bot', async () => {
    const wrapper = await mountPreview(
      state({
        mode: 'brawl',
        roster: [
          rosterEntry('a', 'Alpha'),
          rosterEntry('b', 'Bravo'),
          rosterEntry('c', 'Charlie'),
          rosterEntry('d', 'Delta'),
        ],
        team_a: [fighter('a'), fighter('c')],
        team_b: [fighter('b')],
      })
    )

    currentMatch.choosePartnerType('B', true)
    await flushPromises()
    currentMatch.selectBot(
      'B',
      arenaStoreMock.creatures.find((c) => c.key === 'training-eyebot')!
    )
    await flushPromises()

    expect(arenaStoreMock.setFighters).toHaveBeenLastCalledWith(
      'vault-1',
      'room-1',
      expect.objectContaining({
        mode: 'brawl',
        fighterAId: 'a',
        fighterBId: 'b',
        fighterCId: 'c',
        fighterDId: null,
        teamBBotKey: 'training-eyebot',
      }),
      'test-token'
    )
    expect(wrapper.text()).toContain('Training Eyebot')
  })
})
