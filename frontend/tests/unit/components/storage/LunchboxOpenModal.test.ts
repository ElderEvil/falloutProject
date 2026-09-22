import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import LunchboxOpenModal from '@/modules/storage/components/LunchboxOpenModal.vue'
import type { components } from '@/core/types/api.generated'

type LunchboxOpened = components['schemas']['LunchboxOpened']

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const result: LunchboxOpened = {
  reward_type: 'lunchbox',
  items: [
    { name: 'Laser Pistol', type: 'weapon', rarity: 'rare' },
    { name: 'Vault Suit', type: 'outfit', rarity: 'common' },
    { name: 'Combat Armor', type: 'outfit', rarity: 'legendary' },
  ],
  dweller: { reward_type: 'dweller', dweller_id: 'dweller-1', name: 'Jane Doe' },
}

const mountModal = (options: Parameters<typeof mount>[1] = {}) =>
  mount(LunchboxOpenModal, {
    props: { show: true, result },
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    ...options,
  })

const findButton = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(label))

describe('LunchboxOpenModal', () => {
  let wrapper: VueWrapper | null = null

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('renders a labelled dialog with sealed placeholders before revealing', () => {
    wrapper = mountModal()

    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.exists()).toBe(true)
    const titleId = dialog.attributes('aria-labelledby')
    expect(titleId).toBeTruthy()
    expect(wrapper.find(`[id="${titleId}"]`).text()).toContain('Lunchbox Opened!')
    expect(wrapper.text()).toContain('Reveal Contents')
    expect(wrapper.text()).not.toContain('Laser Pistol')
    expect(wrapper.text()).not.toContain('Jane Doe')
  })

  it('reveals rolled items and the dweller on demand', async () => {
    wrapper = mountModal()

    const reveal = findButton(wrapper, 'Reveal Contents')
    expect(reveal?.exists()).toBe(true)
    await reveal!.trigger('click')

    expect(wrapper.text()).toContain('Laser Pistol')
    expect(wrapper.text()).toContain('rare')
    expect(wrapper.text()).toContain('Vault Suit')
    expect(wrapper.text()).toContain('Jane Doe')
  })

  it('emits close from the Done action', async () => {
    wrapper = mountModal()

    const done = findButton(wrapper, 'Done')
    expect(done?.exists()).toBe(true)
    await done!.trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits close from the dialog close button', async () => {
    wrapper = mountModal()

    const close = wrapper.findAll('button').find((button) => button.text() === 'Close')
    expect(close?.exists()).toBe(true)
    await close!.trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits close on Escape', async () => {
    wrapper = mountModal()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('moves focus into the dialog on open', async () => {
    wrapper = mountModal({ attachTo: document.body })
    await flushPromises()

    const reveal = findButton(wrapper, 'Reveal Contents')
    expect(document.activeElement).toBe(reveal?.element)
  })
})
