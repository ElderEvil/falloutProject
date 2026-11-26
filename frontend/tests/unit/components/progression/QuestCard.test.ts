import { describe, expect, it } from 'vite-plus/test'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Icon } from '@iconify/vue'
import { Progress } from '@/core/components/ui/progress'
import QuestCard from '@/modules/progression/components/QuestCard.vue'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useQuestStore } from '@/modules/progression/stores/quest'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { VaultQuest } from '@/modules/progression/models/quest'

const quest = {
  id: 'quest-1',
  title: 'A Very Long Expedition',
  short_description: 'A description that can be much longer than the other quest cards.',
  long_description: '',
  requirements: '',
  rewards: '100 Caps',
  quest_type: 'side',
  quest_category: null,
  chain_id: null,
  chain_order: 0,
  previous_quest_id: null,
  next_quest_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  is_visible: true,
  is_locked: false,
  lock_reason: null,
  is_completed: false,
  started_at: null,
  duration_minutes: 60,
  quest_requirements: [],
  quest_rewards: [],
} as VaultQuest

/**
 * One card per test: a fresh pinia (the card reads the quest and dweller stores),
 * an optional store seed that must land before mount, and the shared props.
 */
const mountCard = (
  patch: Partial<VaultQuest> = {},
  props: Record<string, unknown> = {},
  seed?: () => void
) => {
  setActivePinia(createPinia())
  seed?.()
  return mount(QuestCard, {
    props: {
      quest: { ...quest, ...patch },
      vaultId: 'vault-1',
      status: 'available',
      partyMembers: [],
      ...props,
    },
  })
}

const icons = (wrapper: VueWrapper) =>
  wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))

const requirement = (requirement_type: string, requirement_data: object, extra: object = {}) => [
  { id: 'req-1', requirement_type, requirement_data, ...extra },
]

const reward = (reward_type: string, reward_data: object) => [
  { id: 'reward-1', reward_type, reward_data, reward_chance: 1 },
]

describe('QuestCard', () => {
  it.each(['combat', 'training'])(
    'limits timed starts while allowing %s state quests',
    async (quest_category) => {
      const wrapper = mountCard({ quest_category }, {}, () => {
        const store = useQuestStore()
        store.vaultQuests = Array.from({ length: 3 }, (_, index) => ({
          ...quest,
          id: `running-${index}`,
          started_at: '2026-01-01T00:00:00Z',
          return_completes_at: index === 0 ? '2099-01-01T00:00:00Z' : null,
        }))
        store.vaultQuests.push(
          { ...quest, id: 'ready', started_at: '2026-01-01T00:00:00Z', is_reward_ready: true },
          { ...quest, id: 'completed', started_at: '2026-01-01T00:00:00Z', is_completed: true },
          { ...quest, id: 'state', started_at: '2026-01-01T00:00:00Z', quest_category: 'training' }
        )
      })
      const store = useQuestStore()
      expect(store.activeTimedQuestCount).toBe(3)
      const action = wrapper.get('.quest-action-btn')
      if (quest_category === 'combat') {
        expect(action.attributes('disabled')).toBeDefined()
        expect(action.text()).toContain('Quest limit reached')
        store.vaultQuests = store.vaultQuests.map((entry) => ({ ...entry, is_reward_ready: true }))
        await wrapper.vm.$nextTick()
        expect(action.attributes('disabled')).toBeUndefined()
      } else {
        expect(action.attributes('disabled')).toBeUndefined()
        await action.trigger('click')
        expect(wrapper.emitted('start')).toEqual([['quest-1']])
      }
    }
  )

  it('renders a completed quest with a non-interactive Completed mark instead of a Details action', () => {
    const wrapper = mountCard({ is_completed: true }, { status: 'completed' })

    expect(wrapper.find('.quest-card button').exists()).toBe(false)
    expect(wrapper.text()).toContain('Completed')
    expect(wrapper.text()).not.toContain('View Details')
    expect(wrapper.emitted('view')).toBeUndefined()
  })

  it('labels the primary action on an available quest', () => {
    const action = mountCard().find('.quest-card button')

    expect(action.exists()).toBe(true)
    expect(action.text()).toContain('Start Quest')
  })

  it.each(['building', 'population', 'training'])(
    'renders %s quests as vault objectives',
    async (quest_category) => {
      const wrapper = mountCard({ quest_category })

      await wrapper.get('button').trigger('click')

      expect(wrapper.emitted('start')).toEqual([['quest-1']])
      expect(wrapper.emitted('assignParty')).toBeUndefined()
      expect(wrapper.text()).not.toContain('Assign party to start')
      expect(wrapper.text()).not.toContain('Duration:')
      expect(wrapper.text()).toContain('Check Objective')
    }
  )

  it('capitalizes a dweller reward template name', () => {
    const wrapper = mountCard({
      quest_rewards: reward('dweller', { template_id: 'lucy-maclean' }),
    })

    expect(wrapper.text()).toContain('Lucy Maclean')
  })

  it('shows elapsed progress for an active timed quest', () => {
    const wrapper = mountCard(
      {
        started_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        duration_minutes: 60,
      },
      { status: 'active' }
    )

    expect(wrapper.findComponent(Progress).props('modelValue')).toBeGreaterThan(0)
    expect(wrapper.find('.quest-progress-bar').exists()).toBe(true)
    expect(wrapper.find('.timer-progress').text()).toMatch(/% complete/)
  })

  it('keeps completed progress visible while rewards await a claim', () => {
    const wrapper = mountCard(
      {
        started_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
        duration_minutes: 60,
      },
      { status: 'ready' }
    )

    expect(wrapper.findComponent(Progress).props('modelValue')).toBe(100)
    expect(wrapper.text()).toContain('Complete')
  })

  it('uses a reward icon when a quest is ready to claim', () => {
    expect(icons(mountCard({}, { status: 'ready' }))).toContain('mdi:treasure-chest')
  })

  it('renders a travelling quest disabled with a return ETA', () => {
    const wrapper = mountCard(
      {
        started_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
        duration_minutes: 60,
        return_started_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
        return_completes_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
      },
      { status: 'returning' }
    )

    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Travelling Home')
    expect(wrapper.find('.timer-value').text()).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })

  it('shows a room requirement by display name instead of slug', () => {
    const wrapper = mountCard({
      quest_requirements: requirement('room', { room_type: 'living_quarter', count: 1 }),
    })

    expect(wrapper.text()).toContain('Build 1 Living Quarter')
    expect(wrapper.text()).not.toContain('living_quarter')
  })

  it('marks an item requirement as met when the quest is available', () => {
    const wrapper = mountCard({
      quest_requirements: requirement('item', { item_name: 'Vault 33 suit' }),
    })

    expect(icons(wrapper)).toContain('mdi:check-circle')
    expect(icons(wrapper)).not.toContain('mdi:lock')
    expect(wrapper.find('.prerequisite-item.met').exists()).toBe(true)
    expect(wrapper.find('.prerequisite-item.unmet').exists()).toBe(false)
    expect(wrapper.text()).toContain('Requires Vault 33 suit')
  })

  it('paints per-row gate verdicts from the backend read, not the lock verdict', () => {
    // The quest is chain-locked, but the backend says the suit is owned: the item
    // row shows met while the unevaluatable attack row stays unmet.
    const wrapper = mountCard(
      {
        quest_requirements: [
          {
            id: 'req-item',
            requirement_type: 'item',
            requirement_data: { item_name: 'Vault 33 suit' },
            is_mandatory: true,
            is_met: true,
          },
          {
            id: 'req-attack',
            requirement_type: 'attack',
            requirement_data: { attack: 6 },
            is_mandatory: true,
            is_met: false,
          },
        ],
      },
      { isLocked: true }
    )

    expect(wrapper.find('.prerequisite-item.met').text()).toContain('Requires Vault 33 suit')
    expect(wrapper.find('.prerequisite-item.unmet').text()).toContain('Requires 6+ Attack')
  })

  it.each([
    [[{ id: 'd1', level: 7 }], { level: 5 }, true],
    [[{ id: 'd1', level: 2 }], { level: 5 }, false],
    [[{ id: 'd1', level: 10 }], { level: 10, count: 3 }, false],
    [
      [
        { id: 'd1', level: 10 },
        { id: 'd2', level: 12 },
        { id: 'd3', level: 3 },
      ],
      { level: 10, count: 2 },
      true,
    ],
  ] as [DwellerShort[], object, boolean][])(
    'unlocks on the level requirement only when enough dwellers meet it (%o)',
    (dwellers, requirement_data, met) => {
      const wrapper = mountCard(
        { quest_requirements: requirement('level', requirement_data) },
        {},
        () => {
          useDwellerFilterStore().dwellers = dwellers
        }
      )

      expect(icons(wrapper).includes('mdi:lock-open')).toBe(met)
      expect(icons(wrapper).includes('mdi:lock')).toBe(!met)
    }
  )

  it.each([
    [true, 'Room to Grow'],
    [false, 'Previous quest'],
  ])('names the prerequisite quest (completed: %s) instead of a generic label', (known, label) => {
    const wrapper = mountCard(
      {
        quest_requirements: requirement('quest_completed', {
          quest_id: known ? 'quest-1' : 'quest-missing',
        }),
      },
      {},
      () => {
        useQuestStore().quests = [{ id: 'quest-1', title: 'Room to Grow' }]
      }
    )

    expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).not.toContain(known ? 'Previous quest' : 'Room to Grow')
  })

  it.each([
    [true, true],
    [false, false],
  ])('unlocks on a completed prerequisite quest (%s)', (completed, met) => {
    const wrapper = mountCard(
      { quest_requirements: requirement('quest_completed', { quest_id: 'quest-1' }) },
      {},
      () => {
        useQuestStore().vaultQuests = [
          { id: 'quest-1', title: 'Room to Grow', is_completed: completed },
        ]
      }
    )

    expect(icons(wrapper).includes('mdi:lock-open')).toBe(met)
    expect(icons(wrapper).includes('mdi:lock')).toBe(!met)
  })

  it('renders the backend lock reason on a locked quest card', () => {
    const wrapper = mountCard(
      { is_locked: true, lock_reason: "Requires Overseer's Office" },
      { status: 'locked', isLocked: true }
    )

    expect(wrapper.text()).toContain("Requires Overseer's Office")
    expect(wrapper.text()).toContain('Locked')
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })

  it('renders the lock reason only once when the backend already names the prerequisite', () => {
    const wrapper = mountCard(
      {
        is_locked: true,
        lock_reason: "Complete 'Snipping Coupons' to unlock",
        previous_quest_id: 'quest-0',
      },
      { status: 'locked', isLocked: true },
      () => {
        useQuestStore().vaultQuests = [{ ...quest, id: 'quest-0', title: 'Snipping Coupons' }]
      }
    )

    expect(wrapper.text()).toContain("Complete 'Snipping Coupons' to unlock")
    expect(wrapper.text().match(/Snipping Coupons/g) || []).toHaveLength(1)
  })

  it('uses a medical icon for a Stimpak item reward instead of the weapon icon', () => {
    const wrapper = mountCard(
      { quest_rewards: reward('item', { item_name: 'Stimpak', rarity: 'common' }) },
      { status: 'ready' }
    )

    expect(wrapper.text()).toContain('Stimpak')
    expect(wrapper.text()).not.toContain('(common)')
    expect(icons(wrapper)).toContain('mdi:medical-bag')
    expect(icons(wrapper)).not.toContain('mdi:sword')
  })

  it.each([
    ['weapon', 'mdi:pistol'],
    ['outfit', 'mdi:tshirt-crew'],
    ['consumable', 'mdi:bottle-tonic'],
  ])('resolves item category %s to %s', (item_type, icon) => {
    const wrapper = mountCard(
      { quest_rewards: reward('item', { item_name: 'Test Item', item_type }) },
      { status: 'ready' }
    )

    expect(icons(wrapper)).toContain(icon)
    expect(icons(wrapper)).not.toContain('mdi:sword')
  })

  it.each([
    ['building', 'mdi:home-group'],
    ['collection', 'mdi:package-variant'],
    ['combat', 'mdi:sword-cross'],
    ['exploration', 'mdi:compass'],
    ['population', 'mdi:account-group'],
    ['training', 'mdi:dumbbell'],
    [null, 'mdi:flag'],
    ['unknown', 'mdi:flag'],
  ])('represents %s with an accessible category icon and a type badge', (category, icon) => {
    const wrapper = mountCard({ quest_category: category as VaultQuest['quest_category'] })

    const header = wrapper.get('.progression-header')
    const label = ['Side quest', category].filter(Boolean).join(' · ')
    expect(header.get('[role="img"]').attributes('aria-label')).toBe(label)
    expect(header.get('[role="img"]').attributes('title')).toBe(label)
    expect(header.findComponent(Icon).props('icon')).toBe(icon)
    expect(header.text()).toContain(quest.title)
    const typeBadge = header.get('[data-slot="badge"]')
    expect(typeBadge.text()).toBe('Side')
    expect(typeBadge.classes()).toEqual(
      expect.arrayContaining(['bg-quest-side', 'text-white', 'border-quest-side'])
    )
    expect(typeBadge.attributes('style')).toBeUndefined()
  })

  it('keeps the chain position after the title and identifies main quests', () => {
    const wrapper = mountCard(
      { chain_id: 'chain', chain_order: 2, quest_type: 'main', quest_category: 'combat' },
      {},
      () => {
        useQuestStore().quests = [1, 2, 3].map((order) => ({
          ...quest,
          id: `chain-${order}`,
          chain_id: 'chain',
          chain_order: order,
        }))
      }
    )

    const header = wrapper.get('.progression-header')
    expect(header.get('[role="img"]').attributes('aria-label')).toBe('Main quest · combat')
    expect(header.text()).toContain('2/3')
    expect(header.findAllComponents(Icon).map((icon) => icon.props('icon'))).toEqual([
      'mdi:sword-cross',
      'mdi:link-variant',
    ])
    expect(header.text()).toContain('Main') // The type badge precedes the chain badge.
    expect(header.text()).toContain('2/3')
  })

  it.each([
    ['available', 'var(--color-quest-side)'],
    ['active', 'var(--color-theme-accent)'],
    ['returning', 'var(--color-theme-secondary)'],
    ['ready', 'var(--color-rarity-legendary)'],
    ['completed', 'var(--color-quest-muted)'],
    ['locked', 'var(--color-quest-locked)'],
  ] as const)('keeps the %s status border colour on the shared card shell', (status, border) => {
    const wrapper = mountCard(
      { is_completed: status === 'completed' },
      { status, isLocked: status === 'locked' }
    )

    expect(wrapper.find('.quest-card').attributes('style')).toContain(`border-color: ${border}`)
  })
})
