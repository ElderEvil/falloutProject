import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouterMock } from '../helpers/mocks'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ObjectivesView from '@/modules/progression/views/ObjectivesView.vue'
import ObjectiveCompleteModal from '@/modules/progression/components/ObjectiveCompleteModal.vue'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import type { Objective } from '@/modules/progression/models/objective'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-123' } }))

const dailyObjective: Objective = {
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

const starterObjective = (sequence: number, completed = false): Objective => ({
  ...dailyObjective,
  id: `starter-${sequence}`,
  category: 'starter',
  sequence,
  challenge: `Starter step ${sequence}`,
  progress: completed ? 1 : 0,
  total: 1,
  is_completed: completed,
  objective_type: 'collect',
})

const officeObjective = (completed = false): Objective => ({
  ...dailyObjective,
  id: 'office',
  category: 'starter',
  sequence: 5,
  challenge: "Build Overseer's Office",
  progress: completed ? 1 : 0,
  total: 1,
  is_completed: completed,
  objective_type: 'build',
  target_entity: { room_type: 'overseers_office' },
})

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
  localStorage.clear()
  setActivePinia(createPinia())
  objectivesStore = useObjectivesStore()
  vi.clearAllMocks()
  vi.spyOn(objectivesStore, 'fetchObjectives').mockResolvedValue()
})

describe('ObjectivesView claim flow', () => {
  it('claiming an objective calls completeObjective and opens the completion modal', async () => {
    objectivesStore.objectives = [{ ...dailyObjective }]
    const completed = { ...dailyObjective, is_completed: true }
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
    objectivesStore.objectives = [{ ...dailyObjective }]
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

describe('ObjectivesView objective gating', () => {
  it('keeps the Starter tab claimable and hides the regular tabs before the Office', async () => {
    objectivesStore.objectives = [
      { ...starterObjective(1), challenge: 'Match a dweller to their room' },
      { ...dailyObjective },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBe(1)
    expect(tabs[0].text()).toContain('Starter')
    expect(wrapper.text()).toContain('Match a dweller to their room')
    expect(wrapper.text()).toContain("build the Overseer's Office")
    expect(wrapper.text()).not.toContain('Collect 100 caps')
  })

  it('ignores a retired starter when picking the current step', async () => {
    objectivesStore.objectives = [
      starterObjective(5, true),
      { ...dailyObjective, id: 'retired', category: 'starter', sequence: null, objective_type: undefined },
      { ...dailyObjective, id: 'daily-1' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[role="tab"]').length).toBe(5)
    expect(wrapper.text()).toContain('Collect 100 caps')
  })

  it('keeps the tabs locked until the Office is completed', async () => {
    objectivesStore.objectives = [officeObjective(false), { ...dailyObjective }]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[role="tab"]').length).toBe(1)
    expect(wrapper.text()).not.toContain('Collect 100 caps')
  })

  it('opens the regular tabs once the Office is completed', async () => {
    objectivesStore.objectives = [
      officeObjective(true),
      starterObjective(6),
      { ...dailyObjective },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[role="tab"]').length).toBe(5)
    expect(wrapper.text()).toContain('Collect 100 caps')
  })

  it('shows a compact current-step action', async () => {
    objectivesStore.objectives = [
      { ...starterObjective(1), challenge: 'Match a dweller to their room' },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Match a dweller to their room')
    const action = wrapper.find('.current-step-action')
    expect(action.exists()).toBe(true)
    expect(action.text()).toContain('Open')
  })

  it('keeps the Starter tab after the spotlight is skipped', async () => {
    localStorage.setItem('onboarding:v1', JSON.stringify({ 'vault-123': { skipped: true } }))
    objectivesStore.objectives = [{ ...starterObjective(1), challenge: 'Match a dweller to their room' }]

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBe(1)
    expect(tabs[0].text()).toContain('Starter')
    expect(wrapper.text()).toContain('Match a dweller to their room')
  })

  it('claims a starter objective from the Starter tab', async () => {
    const objective = { ...starterObjective(1), progress: 1 }
    objectivesStore.objectives = [objective]
    const completeSpy = vi.spyOn(objectivesStore, 'completeObjective').mockResolvedValue({
      ...objective,
      is_completed: true,
    })

    wrapper = mountView()
    await wrapper.vm.$nextTick()

    await wrapper.find('.claim-btn').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(completeSpy).toHaveBeenCalledWith('vault-123', 'starter-1')
  })
})
