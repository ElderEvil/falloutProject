import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PartySelectionModal from '@/modules/progression/components/PartySelectionModal.vue'
import { Slider } from '@/core/components/ui/slider'
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

    expect(wrapper.emitted('assign')).toEqual([[['dweller-1'], { stimpaks: 0, radaways: 0 }]])
    expect(wrapper.emitted('start')).toBeUndefined()
  })

  const mountDispatchWithSupplies = (maxStimpaks: number, maxRadaways: number) =>
    mount(PartySelectionModal, {
      props: {
        modelValue: false,
        quest: null,
        vaultId: 'vault-1',
        dwellers: [socializingDweller],
        currentParty: [],
        maxPartySize: 1,
        showSupplies: true,
        maxStimpaks,
        maxRadaways,
      },
      global: {
        stubs: {
          Teleport: { template: '<div><slot /></div>' },
        },
      },
    })

  const supplyTexts = (wrapper: ReturnType<typeof mountDispatchWithSupplies>) =>
    wrapper.findAll('.w-14').map((el) => el.text())

  it('resets supply selections to zero each time the picker opens', async () => {
    const wrapper = mountDispatchWithSupplies(5, 4)

    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    const sliders = wrapper.findAllComponents(Slider)
    sliders[0].vm.$emit('update:modelValue', [3])
    sliders[1].vm.$emit('update:modelValue', [2])
    await flushPromises()
    expect(supplyTexts(wrapper)).toEqual(['3 / 5', '2 / 4'])

    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    expect(supplyTexts(wrapper)).toEqual(['0 / 5', '0 / 4'])
  })

  it('clamps supply selections when availability shrinks while open', async () => {
    const wrapper = mountDispatchWithSupplies(5, 5)

    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    const sliders = wrapper.findAllComponents(Slider)
    sliders[0].vm.$emit('update:modelValue', [4])
    sliders[1].vm.$emit('update:modelValue', [4])
    await flushPromises()
    expect(supplyTexts(wrapper)).toEqual(['4 / 5', '4 / 5'])

    await wrapper.setProps({ maxStimpaks: 2, maxRadaways: 1 })
    await flushPromises()
    expect(supplyTexts(wrapper)).toEqual(['2 / 2', '1 / 1'])

    await wrapper.setProps({ maxStimpaks: 0 })
    await flushPromises()
    expect(supplyTexts(wrapper)).toEqual(['0 / 0', '1 / 1'])
  })

  it('disables supply sliders at zero availability and keeps the payload at zero', async () => {
    const wrapper = mountDispatchWithSupplies(0, 0)

    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    const sliders = wrapper.findAllComponents(Slider)
    expect(sliders.map((s) => s.props('disabled'))).toEqual([true, true])
    expect(sliders.map((s) => s.props('max'))).toEqual([0, 0])
    expect(supplyTexts(wrapper)).toEqual(['0 / 0', '0 / 0'])

    // A forced update must not push either count above availability.
    sliders[0].vm.$emit('update:modelValue', [1])
    sliders[1].vm.$emit('update:modelValue', [1])
    await flushPromises()
    expect(supplyTexts(wrapper)).toEqual(['0 / 0', '0 / 0'])

    await wrapper.find('.dweller-item').trigger('click')
    const dispatchButton = wrapper.findAll('button').find((b) => b.text().includes('Dispatch'))
    await dispatchButton!.trigger('click')
    expect(wrapper.emitted('assign')).toEqual([[['dweller-1'], { stimpaks: 0, radaways: 0 }]])
  })
})
