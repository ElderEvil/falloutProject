import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount, type MountingOptions } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerCard from '@/modules/dwellers/components/cards/DwellerCard.vue'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { makeDweller } from '../../helpers/dwellerFixtures'

// Mock the happiness service
vi.mock('@/modules/dwellers/services/happinessService', () => ({
  happinessService: {
    getDwellerModifiers: vi.fn().mockResolvedValue({
      data: { positive: [], negative: [] },
    }),
  },
}))

beforeEach(() => {
  setActivePinia(createPinia())
})

type CardProps = InstanceType<typeof DwellerCard>['$props']

const baseDweller = makeDweller({
  id: '123',
  first_name: 'John',
  last_name: 'Doe',
  health: 80,
  happiness: 75,
  gender: 'male',
  rarity: 'common',
  experience: 450,
  stimpack: 2,
  radaway: 1,
  status: 'idle',
  room: null,
})

// Everything mount() accepts except props: callers pass `global.stubs`, and a narrower
// hand-written type rejects it as an excess property while the spread still mounts fine.
const mountCard = (
  overrides: Partial<CardProps> = {},
  options: Omit<MountingOptions<typeof DwellerCard>, 'props'> = {}
): ReturnType<typeof mount> =>
  mount(DwellerCard, {
    props: {
      dweller: baseDweller,
      imageUrl: null,
      loading: false,
      availableStimpaks: 0,
      availableRadaways: 0,
      healingSupply: null,
      ...overrides,
    },
    ...options,
  })

const actionLabels = (wrapper: ReturnType<typeof mount>) =>
  wrapper.findAll('.actions-container button').map((btn) => btn.text().trim())

const disabled = (wrapper: ReturnType<typeof mount>, selector: string) => {
  const element = wrapper.find(selector)
  return element.exists() ? element.attributes('disabled') !== undefined : false
}

const supplyState = (wrapper: ReturnType<typeof mount>) => ({
  supplies: wrapper.find('.supplies').exists(),
  stimRow: wrapper.find('.supply-stimpack').exists(),
  radRow: wrapper.find('.supply-radaway').exists(),
  stimDisabled: disabled(wrapper, '[aria-label="Use Stimpack"]'),
  radDisabled: disabled(wrapper, '[aria-label="Use RadAway"]'),
})

describe('DwellerCard', () => {
  describe('portrait', () => {
    it('renders a non-interactive placeholder when no portrait exists', () => {
      const wrapper = mountCard()

      expect(wrapper.find('.portrait-placeholder').text()).toContain('No portrait')
      expect(wrapper.find('button[aria-label="Generate custom portrait"]').exists()).toBe(false)
    })

    it.each([
      ['https://example.com/image.jpg', 'https://example.com/image.jpg', false],
      [
        '/static/legendary_dweller_images/FOS_Dw_Butch.png',
        'http://localhost:8000/static/legendary_dweller_images/FOS_Dw_Butch.png',
        true,
      ],
    ] as const)(
      'resolves %s against the API origin and %s the curated frame',
      (imageUrl, resolved, framed) => {
        const wrapper = mountCard({ imageUrl })

        expect(wrapper.find('.portrait-image').attributes('src')).toBe(resolved)
        expect(
          wrapper.find('.portrait-container').classes().includes('default-portrait-frame')
        ).toBe(framed)
        expect(wrapper.find('.portrait-image').classes().includes('default-portrait-zoom')).toBe(
          framed
        )
      }
    )

    it('keeps non-humanoid companion art out of the human frame', () => {
      const wrapper = mountCard({
        imageUrl: '/static/legendary_dweller_images/FOS_Dw_Snip_Snip.png',
      })

      expect(wrapper.find('.portrait-container').classes()).not.toContain('default-portrait-frame')
      expect(wrapper.find('.portrait-image').classes()).not.toContain('default-portrait-zoom')
      expect(wrapper.find('.portrait-image').classes()).toContain('portrait-image--contain')
    })

    it('marks a dead dweller portrait as deceased', () => {
      const wrapper = mountCard({
        dweller: { ...baseDweller, is_dead: true },
        imageUrl: 'https://example.com/image.jpg',
      })

      expect(wrapper.find('.portrait-image').classes()).toContain('grayscale')
      expect(wrapper.find('.dead-portrait-marker').exists()).toBe(true)
    })
  })

  describe('stats', () => {
    it.each([
      ['Level', '5'],
      ['Health', '80 / 100'],
      ['Happiness', '75%'],
      ['Stimpack', '2'],
      ['RadAway', '1'],
    ])('reads the %s row with its exact value', (label, value) => {
      const wrapper = mountCard()

      expect(wrapper.text()).toContain(label)
      expect(wrapper.text()).toContain(value)
    })

    it('shows radiation-reduced maximum health', () => {
      const wrapper = mountCard({
        dweller: { ...baseDweller, health: 82, max_health: 120, radiation: 35 },
      })

      expect(wrapper.text()).toContain('82 / 85 (120)')
    })

    it('drives the health bar from the health percentage', () => {
      const wrapper = mountCard()

      const progressBar = wrapper.findComponent({ name: 'HealthRadiationBar' })
      expect(progressBar.exists()).toBe(true)
      expect(progressBar.props('value')).toBe(80)
    })

    it.each([
      [{ level: 5, experience: 450 }, 'Level 5', '1019 XP to L6', false],
      [{ level: 50, experience: 50000 }, 'Level 50', 'Maximum level reached', true],
    ] as const)(
      'reads progress as one level-first block (%o)',
      (progress, levelText, xpText, maxed) => {
        // Reka renders TooltipContent only when open and teleported; stub it inline so the
        // maximum-level description is assertable without hover timers.
        const wrapper = mountCard(
          { dweller: { ...baseDweller, ...progress } },
          { global: { stubs: { TooltipContent: { template: '<div><slot /></div>' } } } }
        )

        const value = wrapper.find('.xp-bar-container .stat-value')
        expect(wrapper.text()).toContain(levelText)
        expect(value.classes().includes('max-level')).toBe(maxed)
        expect(value.text()).not.toMatch(/-\d/)
        expect(wrapper.text()).toContain(xpText)
      }
    )

    it('keeps the training tooltip on the Train action', () => {
      const wrapper = mountCard(
        {},
        { global: { stubs: { TooltipContent: { template: '<div><slot /></div>' } } } }
      )

      expect(wrapper.text()).toContain('Train SPECIAL stats to improve dweller abilities')
    })
  })

  describe('room and away actions', () => {
    const explorationFor = (status?: 'active' | 'returning') => {
      const store = useExplorationStore()
      store.explorations = status
        ? [{ id: 'e1', dweller_id: baseDweller.id, vault_id: 'v1', status } as any]
        : []
    }

    it.each([
      [
        'an idle dweller with no room',
        {},
        undefined,
        ['Chat', 'Choose room', 'Wasteland', 'Train'],
      ],
      [
        'an exploring dweller with an active exploration',
        { status: 'exploring' },
        'active',
        ['Chat', 'Recall'],
      ],
      [
        'an exploring dweller heading home',
        { status: 'exploring' },
        'returning',
        ['Chat', 'Returning'],
      ],
      [
        'an exploring dweller without an exploration record',
        { status: 'exploring' },
        undefined,
        ['Chat'],
      ],
      ['a questing dweller', { status: 'questing' }, undefined, ['Chat']],
      ['a dead dweller', { is_dead: true }, undefined, ['Chat history']],
    ] as const)(
      'offers exactly the vault actions that apply to %s',
      (_name, patch, exploration, expected) => {
        explorationFor(exploration as 'active' | 'returning' | undefined)

        const wrapper = mountCard({ dweller: { ...baseDweller, room: null, ...patch } })

        expect(actionLabels(wrapper)).toEqual([...expected])
      }
    )

    it('offers Unassign and not Assign when the dweller has a room', () => {
      const wrapper = mountCard({ dweller: { ...baseDweller, room: { id: 'r1', name: 'Diner' } } })

      expect(actionLabels(wrapper)).toContain('Unassign')
      expect(actionLabels(wrapper)).not.toContain('Choose room')
    })

    it('does not offer Unassign for a dead dweller that still has a room', () => {
      const wrapper = mountCard({
        dweller: { ...baseDweller, is_dead: true, room: { id: 'r1', name: 'Diner' } },
      })

      expect(actionLabels(wrapper)).not.toContain('Unassign')
    })

    it('labels the assign action as an apprenticeship for youth', () => {
      const wrapper = mountCard({ dweller: { ...baseDweller, age_group: 'child' } })

      expect(actionLabels(wrapper)).toContain('Choose apprentice room')
      expect(actionLabels(wrapper)).not.toContain('Choose room')
    })

    it.each(['child', 'teen'] as const)('disables training and wasteland for a %s', (age_group) => {
      const wrapper = mountCard({ dweller: { ...baseDweller, age_group } })

      const train = wrapper.findAll('button').find((button) => button.text() === 'Train')
      const send = wrapper
        .findAllComponents({ name: 'Button' })
        .find((btn) => btn.text().includes('Wasteland'))
      expect(train?.attributes('disabled')).toBeDefined()
      expect(send!.props('disabled')).toBe(true)
      expect(wrapper.text()).toContain('Training unlocks at adulthood')
    })

    it('enables send to wasteland for an adult', () => {
      const wrapper = mountCard()

      const send = wrapper
        .findAllComponents({ name: 'Button' })
        .find((btn) => btn.text().includes('Wasteland'))

      expect(send!.props('disabled')).toBe(false)
    })
  })

  describe('supplies', () => {
    const state = (overrides: Record<string, boolean> = {}) => ({
      supplies: true,
      stimRow: true,
      radRow: true,
      stimDisabled: false,
      radDisabled: false,
      ...overrides,
    })
    const empty = state({ supplies: false, stimRow: false, radRow: false })
    const synth = (state_of_being: string) => ({
      visual_attributes: { race: 'synth', state_of_being },
      radiation: 30,
      health: 50,
    })

    it.each([
      ['the carried supplies of an injured adult', {}, state({ radDisabled: true })],
      [
        'no RadAway for a visible gen-2 synth',
        synth('gen_2'),
        state({ radRow: false }),
        { availableRadaways: 5 },
      ],
      ['RadAway for an organic gen-3 synth', synth('gen_3'), state(), { availableRadaways: 5 }],
      [
        'a disabled Heal when no supply exists anywhere',
        { stimpack: 0, radaway: 0 },
        state({ radRow: false, stimDisabled: true }),
      ],
      [
        'no supply rows for a healthy empty-pocketed dweller',
        { health: 100, stimpack: 0, radaway: 0 },
        empty,
        { availableStimpaks: 5, availableRadaways: 5 },
      ],
      [
        'no stimpack row for a healthy empty-pocketed dweller',
        { health: 100, stimpack: 0 },
        state({ stimRow: false, radDisabled: true }),
      ],
      [
        'an enabled Heal when hurt and the vault has stock',
        { stimpack: 0 },
        state({ radDisabled: true }),
        { availableStimpaks: 3 },
      ],
      [
        'an empty-pocketed Heal that auto-issues from the vault',
        { stimpack: 0 },
        state({ radDisabled: true }),
        { availableStimpaks: 4 },
      ],
      ['an enabled RadAway when radiation exists', { radiation: 10 }, state()],
      [
        'a Heal up to the pet-adjusted ceiling',
        { health: 100, effective_max_health: 120, stimpack: 0, radaway: 0 },
        state({ radRow: false }),
        { availableStimpaks: 3 },
      ],
      [
        'no medical rows for a dead dweller',
        { is_dead: true, health: 20, radiation: 30, stimpack: 4, radaway: 3 },
        empty,
        { availableStimpaks: 5, availableRadaways: 5 },
      ],
      [
        'no supply offers for a dead dweller with empty pockets',
        { is_dead: true },
        empty,
        { availableStimpaks: 5 },
      ],
    ] as const)('offers %s', (_name, patch, expected, props = {}) => {
      const wrapper = mountCard({ dweller: { ...baseDweller, ...patch }, ...props })

      expect(supplyState(wrapper)).toEqual(expected)
    })

    it('shows the vault count inline on the single Heal button', () => {
      const wrapper = mountCard({ availableStimpaks: 12 })

      const heal = wrapper.find('[aria-label="Use Stimpack"]')
      expect(heal.exists()).toBe(true)
      expect(heal.text()).toContain('vault 12')
    })
  })

  describe('events', () => {
    it.each([
      ['Chat', 'chat', {}],
      ['Choose room', 'assign', {}],
      ['Use Stimpack', 'heal-stimpack', {}],
      ['Use RadAway', 'heal-radaway', { radiation: 10 }],
    ] as const)('emits %s from the %s action', async (label, event, patch) => {
      const wrapper = mountCard({ dweller: { ...baseDweller, ...patch } })

      const button = label.startsWith('Use')
        ? wrapper.find(`[aria-label="${label}"]`)
        : wrapper.findAll('button').find((btn) => btn.text().includes(label))!
      await button.trigger('click')

      expect(wrapper.emitted(event)).toHaveLength(1)
    })
  })
})
