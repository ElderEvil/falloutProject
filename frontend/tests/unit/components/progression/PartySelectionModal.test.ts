import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PartySelectionModal from '@/modules/progression/components/PartySelectionModal.vue'
import { useQuestStore } from '@/modules/progression/stores/quest'
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

describe('PartySelectionModal', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('labels resting dwellers as Socializing', async () => {
    const questStore = useQuestStore()
    vi.spyOn(questStore, 'getEligibleDwellers').mockResolvedValue([socializingDweller] as never)
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
          UModal: { template: '<div><slot /><slot name="footer" /></div>' },
          UBadge: { template: '<span><slot /></span>' },
          UButton: { template: '<button><slot /></button>' },
        },
      },
    })

    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    expect(wrapper.find('.dweller-status').text()).toBe('Socializing')
  })
})
