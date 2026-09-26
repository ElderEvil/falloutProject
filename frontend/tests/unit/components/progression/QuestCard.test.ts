import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Icon } from '@iconify/vue'
import { Progress } from '@/core/components/ui/progress'
import QuestCard from '@/modules/progression/components/QuestCard.vue'
import QuestTypeBadge from '@/modules/progression/components/QuestTypeBadge.vue'
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

describe('QuestCard', () => {
  it('renders a completed quest with a non-interactive Completed mark instead of a Details action', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: { ...quest, is_completed: true },
        vaultId: 'vault-1',
        status: 'completed',
        partyMembers: [],
      },
    })

    expect(wrapper.find('.quest-card button').exists()).toBe(false)
    expect(wrapper.text()).toContain('Completed')
    expect(wrapper.text()).not.toContain('View Details')
    expect(wrapper.emitted('view')).toBeUndefined()
  })

  it('keeps the primary action in a card footer below variable quest content', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: { quest, vaultId: 'vault-1', status: 'available', partyMembers: [] },
    })

    expect(wrapper.find('.quest-card-content').classes()).toContain('flex-1')
    const actionButton = wrapper.find('.quest-card button')
    expect(actionButton.exists()).toBe(true)
    expect(actionButton.text()).toContain('Start Quest')
    // Footer action renders below the variable quest content in DOM order.
    const contentEl = wrapper.find('.quest-card-content').element
    expect(contentEl.compareDocumentPosition(actionButton.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it.each(['building', 'population', 'training'])('renders %s quests as vault objectives', async quest_category => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: { quest: { ...quest, quest_category }, vaultId: 'vault-1', status: 'available' },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('start')).toEqual([['quest-1']])
    expect(wrapper.emitted('assignParty')).toBeUndefined()
    expect(wrapper.text()).not.toContain('Assign party to start')
    expect(wrapper.text()).not.toContain('Duration:')
    expect(wrapper.text()).toContain('Check Objective')
  })

  it('capitalizes a dweller reward template name', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_rewards: [
            {
              id: 'reward-1',
              reward_type: 'dweller',
              reward_data: { template_id: 'lucy-maclean' },
              reward_chance: 1,
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain('Lucy Maclean')
  })

  it('shows elapsed progress for an active timed quest', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          started_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
          duration_minutes: 60,
        },
        vaultId: 'vault-1',
        status: 'active',
        partyMembers: [],
      },
    })

    expect(wrapper.findComponent(Progress).props('modelValue')).toBeGreaterThan(0)
    expect(wrapper.find('.quest-progress-bar').exists()).toBe(true)
    expect(wrapper.find('.timer-progress').text()).toMatch(/% complete/)
  })

  it('keeps completed progress visible while rewards await a claim', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          started_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
          duration_minutes: 60,
        },
        vaultId: 'vault-1',
        status: 'ready',
        partyMembers: [],
      },
    })

    expect(wrapper.findComponent(Progress).props('modelValue')).toBe(100)
    expect(wrapper.text()).toContain('Complete')
  })

  it('uses a reward icon when a quest is ready to claim', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: { quest, vaultId: 'vault-1', status: 'ready', partyMembers: [] },
    })

    expect(wrapper.findAllComponents(Icon).some((icon) => icon.props('icon') === 'mdi:treasure-chest')).toBe(true)
  })

  it('renders a travelling quest disabled with a return ETA', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          started_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
          duration_minutes: 60,
          return_started_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
          return_completes_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
        },
        vaultId: 'vault-1',
        status: 'returning',
        partyMembers: [],
      },
    })

    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Travelling Home')
    expect(wrapper.find('.timer-value').text()).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })

  it('shows a room requirement by display name instead of slug', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'room',
              requirement_data: { room_type: 'living_quarter', count: 1 },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain('Build 1 Living Quarter')
    expect(wrapper.text()).not.toContain('living_quarter')
  })

  it('shows an unlocked lock when a dweller meets the level requirement', () => {
    setActivePinia(createPinia())
    const filterStore = useDwellerFilterStore()
    filterStore.dwellers = [{ id: 'd1', level: 7 } as DwellerShort]
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'level',
              requirement_data: { level: 5 },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).toContain('mdi:lock-open')
  })

  it('keeps the locked lock when no dweller meets the level requirement', () => {
    setActivePinia(createPinia())
    const filterStore = useDwellerFilterStore()
    filterStore.dwellers = [{ id: 'd1', level: 2 } as DwellerShort]
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'level',
              requirement_data: { level: 5 },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).not.toContain('mdi:lock-open')
    expect(icons).toContain('mdi:lock')
  })

  it('names the exact prerequisite quest instead of a generic label', () => {
    setActivePinia(createPinia())
    const questStore = useQuestStore()
    questStore.quests = [{ id: 'quest-1', title: 'Room to Grow' }]
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'quest_completed',
              requirement_data: { quest_id: 'quest-1' },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain('Room to Grow')
    expect(wrapper.text()).not.toContain('Previous quest')
  })

  it('falls back to a generic label when the prerequisite quest is unknown', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'quest_completed',
              requirement_data: { quest_id: 'quest-missing' },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain('Previous quest')
  })

  it('shows an unlocked lock when the prerequisite quest is completed', () => {
    setActivePinia(createPinia())
    const questStore = useQuestStore()
    questStore.vaultQuests = [{ id: 'quest-1', title: 'Room to Grow', is_completed: true }]
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'quest_completed',
              requirement_data: { quest_id: 'quest-1' },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).toContain('mdi:lock-open')
  })

  it('keeps the locked lock when the prerequisite quest is not completed', () => {
    setActivePinia(createPinia())
    const questStore = useQuestStore()
    questStore.vaultQuests = [{ id: 'quest-1', title: 'Room to Grow', is_completed: false }]
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'quest_completed',
              requirement_data: { quest_id: 'quest-1' },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).not.toContain('mdi:lock-open')
    expect(icons).toContain('mdi:lock')
  })

  it('keeps the locked lock when fewer dwellers meet the level than required', () => {
    setActivePinia(createPinia())
    const filterStore = useDwellerFilterStore()
    filterStore.dwellers = [{ id: 'd1', level: 10 } as DwellerShort]
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'level',
              requirement_data: { level: 10, count: 3 },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).not.toContain('mdi:lock-open')
    expect(icons).toContain('mdi:lock')
  })

  it('shows an unlocked lock when enough dwellers meet the level', () => {
    setActivePinia(createPinia())
    const filterStore = useDwellerFilterStore()
    filterStore.dwellers = [
      { id: 'd1', level: 10 } as DwellerShort,
      { id: 'd2', level: 12 } as DwellerShort,
      { id: 'd3', level: 3 } as DwellerShort,
    ]
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_requirements: [
            {
              id: 'req-1',
              requirement_type: 'level',
              requirement_data: { level: 10, count: 2 },
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).toContain('mdi:lock-open')
  })

  it('renders the backend lock reason on a locked quest card', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          is_locked: true,
          lock_reason: "Requires Overseer's Office",
        },
        vaultId: 'vault-1',
        status: 'locked',
        isLocked: true,
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain("Requires Overseer's Office")
    expect(wrapper.text()).toContain('Locked')
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })

  it('uses a medical icon for a Stimpak item reward instead of the weapon icon', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_rewards: [
            {
              id: 'reward-1',
              reward_type: 'item',
              reward_data: { item_name: 'Stimpak', rarity: 'common' },
              reward_chance: 1,
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'ready',
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain('Stimpak')
    expect(wrapper.text()).not.toContain('(common)')
    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).toContain('mdi:medical-bag')
    expect(icons).not.toContain('mdi:sword')
  })

  it.each([
    ['weapon', 'mdi:pistol'],
    ['outfit', 'mdi:tshirt-crew'],
    ['consumable', 'mdi:bottle-tonic'],
  ])('resolves item category %s to %s', (itemType, expectedIcon) => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_rewards: [
            {
              id: 'reward-1',
              reward_type: 'item',
              reward_data: { item_name: 'Test Item', item_type: itemType },
              reward_chance: 1,
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'ready',
        partyMembers: [],
      },
    })

    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).toContain(expectedIcon)
    expect(icons).not.toContain('mdi:sword')
  })

  it('renders the lock reason only once when the backend already names the prerequisite', () => {
    setActivePinia(createPinia())
    const questStore = useQuestStore()
    questStore.vaultQuests = [{ ...quest, id: 'quest-0', title: 'Snipping Coupons' }]
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          is_locked: true,
          lock_reason: "Complete 'Snipping Coupons' to unlock",
          previous_quest_id: 'quest-0',
        },
        vaultId: 'vault-1',
        status: 'locked',
        isLocked: true,
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain("Complete 'Snipping Coupons' to unlock")
    expect(wrapper.text().match(/Snipping Coupons/g) || []).toHaveLength(1)
  })

  it('renders the side quest type chip with the bordered outline styling', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: { quest: { ...quest, quest_type: 'side' }, vaultId: 'vault-1', status: 'available', partyMembers: [] },
    })

    expect(wrapper.find('.type-badge').attributes('style')).toBeUndefined()
    expect(wrapper.findComponent(QuestTypeBadge).props('questType')).toBe('side')
  })

  it.each(['building', 'exploration'])('renders the %s category chip with the bordered outline styling', (category) => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: { quest: { ...quest, quest_category: category }, vaultId: 'vault-1', status: 'available', partyMembers: [] },
    })

    expect(wrapper.find('.category-badge').text()).toBe(category)
    expect(wrapper.text()).toContain(category)
  })
})
