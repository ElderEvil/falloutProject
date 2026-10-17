import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RewardItemCard from '@/core/components/common/RewardItemCard.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
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
    const card = wrapper.getComponent(RewardItemCard)
    expect(card.props('kind')).toBe('dweller')
    expect(card.props('name')).toBe('Wanderer')
    expect(wrapper.findComponent(DwellerPortrait).exists()).toBe(true)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('Wanderer has joined your vault')
    await wrapper.get('button.confirm').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
    expect(router.push).toHaveBeenCalledWith('/vault/vault-1/dwellers')
    expect(wrapper.get('button.confirm').text()).toContain('View dwellers')
    wrapper.unmount()
  })

  it('renders an ordinary reward as a currency tile and closes without navigation', async () => {
    const wrapper = mountModal('50 caps')
    const card = wrapper.getComponent(RewardItemCard)
    expect(card.props('kind')).toBe('currency')
    expect(card.props('name')).toBe('50 caps')
    expect(wrapper.find('.reward-card').exists()).toBe(false)
    await wrapper.get('button.cancel').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(router.push).not.toHaveBeenCalled()
    await wrapper.get('button.confirm').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
    expect(router.push).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('reveals guaranteed equipment with its item name and rarity', () => {
    const wrapper = mountModal('weapon:rare:Hardened shotgun')
    expect(wrapper.getComponent(RewardItemCard).props()).toMatchObject({
      kind: 'item',
      name: 'Hardened shotgun',
      rarity: 'rare',
      itemType: 'weapon',
    })
    expect(wrapper.text()).not.toContain('weapon:rare:')
    wrapper.unmount()
  })
})
