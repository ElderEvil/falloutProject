import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ObjectivesView from '@/modules/progression/views/ObjectivesView.vue'
import ObjectiveCompleteModal from '@/modules/progression/components/ObjectiveCompleteModal.vue'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import type { Objective } from '@/modules/progression/models/objective'

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: 'vault-123' },
  }),
}))

const claimableObjective: Objective = {
  id: 'obj-1',
  vault_id: 'vault-123',
  challenge: 'Collect 100 caps',
  progress: 100,
  total: 100,
  reward: '50 Caps',
  is_completed: false,
  category: 'daily',
  created_at: '',
}

let wrapper: VueWrapper
let objectivesStore: ReturnType<typeof useObjectivesStore>

function mountView() {
  return mount(ObjectivesView, {
    attachTo: document.body,
    global: {
      stubs: {
        SidePanel: true,
        PageContentRail: { template: '<div><slot /></div>' },
        PageHeader: true,
        Icon: true,
      },
    },
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  objectivesStore = useObjectivesStore()
  vi.clearAllMocks()
  vi.spyOn(objectivesStore, 'fetchObjectives').mockResolvedValue()
})

describe('ObjectivesView claim flow', () => {
  it('claiming an objective calls completeObjective and opens the completion modal', async () => {
    objectivesStore.objectives = [{ ...claimableObjective }]
    const completed = { ...claimableObjective, is_completed: true }
    const completeSpy = vi.spyOn(objectivesStore, 'completeObjective').mockResolvedValue(completed)

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const claimButton = wrapper.find('.claim-btn')
    expect(claimButton.exists()).toBe(true)
    await claimButton.trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(completeSpy).toHaveBeenCalledWith('vault-123', 'obj-1')

    const modal = wrapper.findComponent(ObjectiveCompleteModal)
    expect(modal.exists()).toBe(true)
    expect(modal.props('show')).toBe(true)
    expect(modal.props('objective')).toMatchObject({ id: 'obj-1', reward: '50 Caps' })
    expect(wrapper.text()).toContain('50 Caps')
  })

  it('a failed claim surfaces an error toast and opens no modal', async () => {
    objectivesStore.objectives = [{ ...claimableObjective }]
    vi.spyOn(objectivesStore, 'completeObjective').mockRejectedValue(new Error('Claim failed'))

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    await wrapper.find('.claim-btn').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const modal = wrapper.findComponent(ObjectiveCompleteModal)
    expect(modal.props('show')).toBe(false)
    expect(wrapper.text()).toContain('Claim failed')
  })
})

describe('ObjectivesView starter arc', () => {
  it('renders the lowest-sequence incomplete starter step as the Next-step hero and hides the tabs', async () => {
    objectivesStore.objectives = [
      {
        ...claimableObjective,
        id: 'starter-1',
        category: 'starter',
        sequence: 1,
        challenge: 'Assign dwellers to Power',
        description: 'Open the Power Generator and assign dwellers.',
        progress: 0,
        total: 3,
      },
      {
        ...claimableObjective,
        id: 'starter-2',
        category: 'starter',
        sequence: 2,
        challenge: 'Collect 150 Power',
        description: 'Power keeps every room running.',
        progress: 0,
        total: 150,
      },
      { ...claimableObjective, id: 'daily-1', challenge: 'Collect 100 caps' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.next-step-hero').exists()).toBe(true)
    expect(wrapper.text()).toContain('NEXT STEP')
    expect(wrapper.text()).toContain('Assign dwellers to Power')
    expect(wrapper.text()).toContain('Open the Power Generator and assign dwellers.')
    expect(wrapper.text()).not.toContain('Collect 150 Power')
    expect(wrapper.find('.utabs').exists()).toBe(false)
  })

  it('renders the tabbed grid when no starter step is incomplete', async () => {
    objectivesStore.objectives = [
      {
        ...claimableObjective,
        id: 'starter-1',
        category: 'starter',
        sequence: 1,
        challenge: 'Assign dwellers to Power',
        progress: 3,
        total: 3,
        is_completed: true,
      },
      { ...claimableObjective, id: 'daily-1', challenge: 'Collect 100 caps' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.next-step-hero').exists()).toBe(false)
    expect(wrapper.find('.utabs').exists()).toBe(true)
    expect(wrapper.text()).toContain('Collect 100 caps')
  })

  it('lets the player claim a finished current step from the hero', async () => {
    objectivesStore.objectives = [
      {
        ...claimableObjective,
        id: 'starter-1',
        category: 'starter',
        sequence: 1,
        challenge: 'Assign dwellers to Power',
        progress: 3,
        total: 3,
      },
    ]
    const completed = { ...objectivesStore.objectives[0], is_completed: true }
    const completeSpy = vi.spyOn(objectivesStore, 'completeObjective').mockResolvedValue(completed)

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const claimButton = wrapper.find('.next-step-hero .claim-btn')
    expect(claimButton.exists()).toBe(true)
    await claimButton.trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(completeSpy).toHaveBeenCalledWith('vault-123', 'starter-1')
    const modal = wrapper.findComponent(ObjectiveCompleteModal)
    expect(modal.props('show')).toBe(true)
  })
})
