import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { reactive } from 'vue'
import ObjectiveGuide from '@/modules/progression/components/ObjectiveGuide.vue'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import type { Objective } from '@/modules/progression/models/objective'

const route = reactive({ path: '/vault/v1', params: { id: 'v1' } })
vi.mock('vue-router', () => ({ useRoute: () => route }))
const objective = (id: string, sequence: number): Objective => ({
  id,
  vault_id: 'v1',
  challenge: `Step ${sequence}`,
  description: 'Choose a healthy explorer.',
  progress: 0,
  total: 2,
  reward: '50 caps',
  is_completed: false,
  category: 'starter',
  sequence,
  objective_type: 'collect',
  target_entity: { resource_type: 'caps' },
  created_at: '',
})

beforeEach(() => {
  setActivePinia(createPinia())
  route.path = '/vault/v1'
  route.params.id = 'v1'
  vi.spyOn(useObjectivesStore(), 'fetchObjectives').mockResolvedValue()
})

const mountGuide = () =>
  mount(ObjectiveGuide, {
    global: {
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }, Icon: true },
    },
  })

describe('ObjectiveGuide', () => {
  it('surfaces the ordered current step and a relevant action outside the objectives menu', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('second', 1), objective('first', 0)]
    const wrapper = mountGuide()
    await flushPromises()
    expect(wrapper.text()).toContain('Step 0')
    expect(wrapper.text()).not.toContain('Step 1')
    expect(wrapper.text()).toContain('Choose a healthy explorer.')
    expect(wrapper.find('a[href="/vault/v1/exploration"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('keeps an earned step visible until a successful claim and disables duplicate submission', async () => {
    const store = useObjectivesStore()
    store.objectives = [{ ...objective('first', 0), progress: 2 }, objective('second', 1)]
    let complete!: (value: Objective) => void
    const claim = vi.spyOn(store, 'completeObjective').mockImplementation(
      () =>
        new Promise((resolve) => {
          complete = resolve
        })
    )
    const wrapper = mountGuide()
    await flushPromises()
    const button = wrapper.find('button')
    expect(button.text()).toContain('Claim 50 caps')
    await button.trigger('click')
    expect(button.attributes('disabled')).toBeDefined()
    expect(claim).toHaveBeenCalledOnce()
    complete({ ...objective('first', 0), is_completed: true })
    await flushPromises()
    wrapper.unmount()
  })

  it('does not render objectives on a non-vault route or reuse a dweller id as a vault id', async () => {
    route.path = '/dweller/v1/chat'
    const wrapper = mountGuide()
    await flushPromises()
    expect(wrapper.find('section').exists()).toBe(false)
    expect(useObjectivesStore().fetchObjectives).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
