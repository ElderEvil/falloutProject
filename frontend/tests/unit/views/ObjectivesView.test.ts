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

describe('ObjectivesView claim flow', () => {
  let wrapper: VueWrapper
  let objectivesStore: ReturnType<typeof useObjectivesStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    objectivesStore = useObjectivesStore()
    vi.clearAllMocks()
    vi.spyOn(objectivesStore, 'fetchObjectives').mockResolvedValue()
  })

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
