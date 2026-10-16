import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ObjectiveCompleteModal from '@/modules/progression/components/ObjectiveCompleteModal.vue'
import type { Objective } from '@/modules/progression/models/objective'

const router = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => router }))

const objective = (reward: string): Objective => ({
  id: 'housing',
  vault_id: 'vault-1',
  challenge: 'Build a Living Quarters',
  progress: 1,
  total: 1,
  reward,
  is_completed: true,
  category: 'starter',
  created_at: '',
})

const mountModal = (reward: string) =>
  mount(ObjectiveCompleteModal, {
    props: { objective: objective(reward), show: true },
    global: { stubs: { TerminalModal: { template: '<div><slot /><slot name="footer" /></div>' } } },
  })

describe('ObjectiveCompleteModal handoff', () => {
  beforeEach(() => vi.clearAllMocks())

  it('celebrates a granted dweller and links to the actual vault roster without guessing an id', async () => {
    const wrapper = mountModal('dweller:Wanderer')
    expect(wrapper.text()).toContain('Wanderer has joined your vault')
    await wrapper.get('button.confirm').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
    expect(router.push).toHaveBeenCalledWith('/vault/vault-1/dwellers')
    expect(wrapper.get('button.confirm').text()).toContain('View dwellers')
    wrapper.unmount()
  })

  it('keeps ordinary reward confirmation and closing free of navigation', async () => {
    const wrapper = mountModal('50 caps')
    await wrapper.get('button.cancel').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(router.push).not.toHaveBeenCalled()
    await wrapper.get('button.confirm').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
    expect(router.push).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
