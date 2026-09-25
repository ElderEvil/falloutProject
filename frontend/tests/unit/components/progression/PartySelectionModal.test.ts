import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PartySelectionModal from '@/modules/progression/components/PartySelectionModal.vue'
import { useQuestStore, type EligibleDweller } from '@/modules/progression/stores/quest'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { VaultQuest } from '@/modules/progression/models/quest'

vi.mock('@iconify/vue', () => ({ Icon: { template: '<i />' } }))

const socializingDweller = {
  id: 'dweller-1',
  first_name: 'Lucy',
  last_name: 'MacLean',
  level: 1,
  status: 'resting',
} as DwellerShort

const socializingEligibleDweller: EligibleDweller = {
  id: 'dweller-1',
  first_name: 'Lucy',
  last_name: 'MacLean',
  level: 1,
  rarity: 'common',
}

describe('PartySelectionModal', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('labels resting dwellers as Socializing', async () => {
    const questStore = useQuestStore()
    vi.spyOn(questStore, 'getEligibleDwellers').mockResolvedValue([socializingEligibleDweller])
    const wrapper = mount(PartySelectionModal, {
      props: {
        modelValue: false,
        quest: { id: 'quest-1', title: 'Test Quest', duration_minutes: 1 } as VaultQuest,
        vaultId: 'vault-1',
        dwellers: [socializingDweller],
        currentParty: [],
      },
      global: {
        stubs: {
          Teleport: { template: '<div><slot /></div>' },
        },
      },
    })

    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    expect(wrapper.find('.dweller-status').text()).toBe('Socializing')
  })

  it('lists the dwellers prop directly and emits assign without start when quest is absent', async () => {
    const questStore = useQuestStore()
    const getEligibleSpy = vi.spyOn(questStore, 'getEligibleDwellers')
    const wrapper = mount(PartySelectionModal, {
      props: {
        modelValue: false,
        quest: null,
        vaultId: 'vault-1',
        dwellers: [socializingDweller],
        currentParty: [],
        maxPartySize: 1,
      },
      global: {
        stubs: {
          Teleport: { template: '<div><slot /></div>' },
        },
      },
    })

    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    // Dispatch mode skips the eligibility fetch and lists the caller's dwellers.
    expect(getEligibleSpy).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Lucy MacLean')
    expect(wrapper.text()).not.toContain('Level Requirements Met')

    // Select the dweller and confirm the dispatch.
    await wrapper.find('.dweller-item').trigger('click')
    const dispatchButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Dispatch'))
    expect(dispatchButton?.attributes('disabled')).toBeUndefined()
    await dispatchButton!.trigger('click')

    expect(wrapper.emitted('assign')).toEqual([[['dweller-1']]])
    expect(wrapper.emitted('start')).toBeUndefined()
  })
})
