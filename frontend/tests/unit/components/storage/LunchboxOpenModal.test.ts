import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createIconifyMock } from '../../helpers/mocks'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import LunchboxOpenModal from '@/modules/storage/components/LunchboxOpenModal.vue'
import type { components } from '@/core/types/api.generated'

type LunchboxOpened = components['schemas']['LunchboxOpened']

const soundMock = vi.hoisted(() => ({
  playSound: vi.fn(),
}))

vi.mock('@/core/composables/useSound', () => ({
  useSound: () => ({ playSound: soundMock.playSound }),
}))

vi.mock('@iconify/vue', () => createIconifyMock())

const result: LunchboxOpened = {
  reward_type: 'lunchbox',
  items: [
    {
      name: 'Laser Pistol',
      type: 'weapon',
      rarity: 'rare',
      image_url: '/static/weapon_images/laser-pistol.png',
    },
    { name: 'Vault Suit', type: 'outfit', rarity: 'common' },
    { name: 'Combat Armor', type: 'outfit', rarity: 'legendary' },
  ],
  dweller: {
    reward_type: 'dweller',
    dweller_id: 'dweller-1',
    name: 'Jane Doe',
    rarity: 'rare',
    image_url: '/static/dwellers/jane.png',
    thumbnail_url: '/static/dwellers/jane-thumb.png',
  },
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

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    soundMock.playSound.mockClear()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.useRealTimers()
  })

  it('renders a labelled dialog with sealed placeholders before revealing', () => {
    wrapper = mountModal()

    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.exists()).toBe(true)
    const titleId = dialog.attributes('aria-labelledby')
    expect(titleId).toBeTruthy()
    expect(wrapper.find(`[id="${titleId}"]`).text()).toContain('Vault-Tec supply drop')
    expect(wrapper.text()).toContain('Reveal Contents')
    expect(wrapper.text()).not.toContain('Laser Pistol')
    expect(wrapper.text()).not.toContain('Jane Doe')
  })

  it('reveals rolled items and the dweller on demand', async () => {
    wrapper = mountModal()

    const reveal = findButton(wrapper, 'Reveal Contents')
    expect(reveal?.exists()).toBe(true)
    await reveal!.trigger('click')
    await vi.advanceTimersByTimeAsync(2700)

    expect(wrapper.text()).toContain('Laser Pistol')
    expect(wrapper.text()).toContain('rare')
    expect(wrapper.text()).toContain('Vault Suit')
    expect(wrapper.text()).toContain('Jane Doe')
    expect(wrapper.find('img[alt="Laser Pistol"]').attributes('src')).toContain('laser-pistol.png')
    expect(wrapper.find('img[alt="Jane Doe"]').attributes('src')).toContain('jane-thumb.png')
    expect(wrapper.find('[aria-label="Rarity: Rare"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('3 items added to Storage')
  })

  it('reveals each item then the dweller in the same slots, without replacing the supply-drop panel', async () => {
    wrapper = mountModal()
    const slots = wrapper.findAll('[data-reward-slot]').map((slot) => slot.element)
    const reveal = findButton(wrapper, 'Reveal Contents')!
    await reveal.trigger('click')
    expect(reveal.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toContain('Laser Pistol')
    await vi.advanceTimersByTimeAsync(0)
    expect(wrapper.text()).toContain('Laser Pistol')
    expect(wrapper.text()).not.toContain('Vault Suit')
    await vi.advanceTimersByTimeAsync(899)
    expect(wrapper.text()).not.toContain('Vault Suit')
    await vi.advanceTimersByTimeAsync(1)
    expect(wrapper.text()).toContain('Vault Suit')
    expect(wrapper.text()).not.toContain('Combat Armor')
    await vi.advanceTimersByTimeAsync(900)
    expect(wrapper.text()).toContain('Combat Armor')
    expect(wrapper.text()).not.toContain('Jane Doe')
    await vi.advanceTimersByTimeAsync(900)
    expect(wrapper.text()).toContain('Jane Doe')
    expect(wrapper.text()).toContain('Vault-Tec supply drop')
    expect(wrapper.findAll('[data-reward-slot]').map((slot) => slot.element)).toEqual(slots)
    expect(findButton(wrapper, 'Done')!.element).toBe(reveal.element)
    expect(reveal.attributes('disabled')).toBeUndefined()
  })

  it('cancels the old sequence and waits for a result after reopening a sealed box', async () => {
    wrapper = mountModal()
    await findButton(wrapper, 'Reveal Contents')!.trigger('click')
    await vi.advanceTimersByTimeAsync(0)
    soundMock.playSound.mockClear()
    await wrapper.setProps({ show: false, result: null })
    await wrapper.setProps({ show: true })
    await vi.advanceTimersByTimeAsync(3600)
    expect(soundMock.playSound).not.toHaveBeenCalled()
    await findButton(wrapper, 'Reveal Contents')!.trigger('click')
    expect(wrapper.emitted('reveal')).toHaveLength(1)
    expect(wrapper.text()).toContain('Something rattles inside')
    await wrapper.setProps({
      result: { ...result, items: [{ name: 'New Suit', type: 'outfit', rarity: 'common' }] },
    })
    await vi.advanceTimersByTimeAsync(900)
    expect(wrapper.text()).toContain('New Suit')
    expect(wrapper.text()).toContain('Jane Doe')
  })

  it('falls back to item icons and a dweller silhouette when images fail', async () => {
    wrapper = mountModal()
    await findButton(wrapper, 'Reveal Contents')!.trigger('click')
    await vi.advanceTimersByTimeAsync(2700)
    await wrapper.find('img[alt="Laser Pistol"]').trigger('error')
    await wrapper.find('img[alt="Jane Doe"]').trigger('error')

    expect(wrapper.find('img[alt="Laser Pistol"]').exists()).toBe(false)
    expect(wrapper.find('[role="img"][aria-label="Jane Doe"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Laser Pistol')
    expect(wrapper.text()).toContain('Jane Doe')
  })

  it.each([
    ['common', 'cardCommon'],
    ['rare', 'cardRare'],
    ['legendary', 'cardLegendary'],
  ])('plays the %s dweller reveal sound without a generic card drop', async (rarity, sound) => {
    wrapper = mountModal({
      props: {
        show: true,
        result: {
          ...result,
          items: [{ name: 'Vault Suit', type: 'outfit', rarity: 'common' }],
          dweller: { ...result.dweller, rarity },
        },
      },
    })
    await findButton(wrapper, 'Reveal Contents')!.trigger('click')
    await vi.advanceTimersByTimeAsync(0)
    soundMock.playSound.mockClear()
    await vi.advanceTimersByTimeAsync(900)
    expect(soundMock.playSound).toHaveBeenCalledExactlyOnceWith(sound, 'sfx')
  })

  it('plays each rarity fanfare with its own card rather than borrowing the dweller reveal', async () => {
    vi.useFakeTimers()
    wrapper = mountModal()

    const reveal = findButton(wrapper, 'Reveal Contents')
    await reveal!.trigger('click')

    expect(soundMock.playSound).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(0)
    expect(soundMock.playSound).toHaveBeenNthCalledWith(1, 'cardWeapon', 'ui')

    await vi.advanceTimersByTimeAsync(900)
    expect(soundMock.playSound).toHaveBeenNthCalledWith(2, 'cardOutfit', 'ui')

    await vi.advanceTimersByTimeAsync(900)
    expect(soundMock.playSound).toHaveBeenNthCalledWith(3, 'cardOutfit', 'ui')
    expect(soundMock.playSound).toHaveBeenNthCalledWith(4, 'cardLegendary', 'sfx')

    await vi.advanceTimersByTimeAsync(900)
    expect(soundMock.playSound).toHaveBeenNthCalledWith(4, 'cardLegendary', 'sfx')
    expect(soundMock.playSound).toHaveBeenNthCalledWith(5, 'cardRare', 'sfx')
    expect(soundMock.playSound).toHaveBeenCalledTimes(5)
  })

  it('clears pending reveal timers when the modal closes', async () => {
    vi.useFakeTimers()
    wrapper = mountModal()

    const reveal = findButton(wrapper, 'Reveal Contents')
    await reveal!.trigger('click')

    await wrapper.setProps({ show: false })
    await vi.advanceTimersByTimeAsync(3600)

    expect(soundMock.playSound).not.toHaveBeenCalled()
  })

  it('emits close from the Done action', async () => {
    wrapper = mountModal()
    await findButton(wrapper, 'Reveal Contents')!.trigger('click')
    await vi.advanceTimersByTimeAsync(2700)

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
