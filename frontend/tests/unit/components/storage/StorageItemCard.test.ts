import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import StorageItemCard from '@/modules/storage/components/StorageItemCard.vue'

const tooltipText = async (button: { trigger: (event: string) => Promise<void> }) => {
  vi.useFakeTimers()
  await button.trigger('focusin')
  vi.advanceTimersByTime(250)
  await nextTick()
  const text = document.querySelector('[role="tooltip"]')?.textContent?.trim()
  vi.useRealTimers()
  return text
}

describe('StorageItemCard', () => {
  afterEach(() => {
    document.querySelectorAll('[role="tooltip"]').forEach((element) => element.remove())
  })

  it('presents the item description and clearly labelled inventory actions', async () => {
    const wrapper = mount(StorageItemCard, {
      props: {
        item: {
          name: 'Sawed-off Shotgun',
          description: 'Built for close-range combat.',
          rarity: 'common',
          value: 120,
          weapon_subtype: 'shotgun',
        },
        itemType: 'weapon',
      },
      attachTo: document.body,
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('Built for close-range combat.')

    const buttons = wrapper.findAll('button')
    const scrap = buttons.find((button) => button.text().includes('Scrap'))!
    const sell = buttons.find((button) => button.text().trim() === 'Sell')!

    expect(await tooltipText(scrap)).toBe('Scrap')
    expect(await tooltipText(sell)).toBe('Sell')

    const actions = buttons.map((button) => button.text())
    expect(actions.indexOf('Sell')).toBeLessThan(actions.indexOf('Scrap'))
  })

  it('includes the junk quantity in the sell-all title', async () => {
    const wrapper = mount(StorageItemCard, {
      props: { item: { name: 'Desk Fan', value: 10 }, itemType: 'junk', count: 3 },
      attachTo: document.body,
      global: { stubs: { Icon: true } },
    })

    const sellAll = wrapper.findAll('button').find((button) => button.text().includes('Sell all'))!

    expect(await tooltipText(sellAll)).toBe('Sell all (3)')
  })

  it('renders the unified weapon stats including accuracy', () => {
    const wrapper = mount(StorageItemCard, {
      props: {
        item: {
          name: '10mm Pistol',
          rarity: 'rare',
          value: 50,
          weapon_subtype: 'pistol',
          damage_min: 2,
          damage_max: 5,
          stat: 'agility',
          accuracy: 70,
          weapon_type: 'gun',
        },
        itemType: 'weapon',
      },
      global: { stubs: { Icon: true } },
    })

    const text = wrapper.text()
    expect(text).toContain('Damage:')
    expect(text).toContain('2-5')
    expect(text).toContain('Accuracy:')
    expect(text).toContain('70%')
    expect(text).toContain('Type:')
  })

  it('renders outfit SPECIAL bonuses alongside gender', () => {
    const wrapper = mount(StorageItemCard, {
      props: {
        item: {
          name: 'Lab Coat',
          rarity: 'rare',
          outfit_type: 'rare_outfit',
          intelligence: 2,
          gender: 'female',
        },
        itemType: 'outfit',
      },
      global: { stubs: { Icon: true } },
    })

    const text = wrapper.text()
    expect(text).toContain('I:')
    expect(text).toContain('+2')
    expect(text).toContain('Gender:')
    expect(text).toContain('female')
  })

  it('renders generic supplies without inventory actions', () => {
    const wrapper = mount(StorageItemCard, {
      props: {
        item: { name: 'Nuka-Cola Quantum', rarity: 'rare', value: 50, item_type: 'consumable' },
        itemType: 'consumable',
        count: 2,
      },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('Nuka-Cola Quantum')
    expect(wrapper.text()).toContain('×2')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })
})
