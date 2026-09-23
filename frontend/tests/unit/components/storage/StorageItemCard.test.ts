import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import StorageItemCard from '@/modules/storage/components/StorageItemCard.vue'

// jsdom lacks ResizeObserver, which reka-ui's TooltipContent uses to measure
// itself on mount (same polyfill pattern as AISettingsPanel.test.ts for
// reka-ui's missing browser APIs).
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

const findButton = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(label))!

// reka-ui's TooltipTrigger opens on native `focus` (immediate, no delay) and on
// `pointermove` (delayed by TooltipProvider's delayDuration). jsdom's synthetic
// events carry no pointerType, so dispatch real events — the same approach the
// sibling AISettingsPanel.test.ts uses for reka-ui pointer/keyboard behaviour.
const expectTooltip = async (button: ReturnType<typeof findButton>, text: string) => {
  button.element.dispatchEvent(new FocusEvent('focus'))
  await nextTick()
  const tooltip = document.querySelector<HTMLElement>('[role="tooltip"]')
  expect(tooltip?.textContent).toContain(text)
  expect(button.attributes('aria-describedby')).toBe(tooltip?.id)
  button.element.dispatchEvent(new FocusEvent('blur'))
  await nextTick()
}

describe('StorageItemCard', () => {
  beforeEach(() => {
    // Tooltip content is teleported to <body>; drop leftovers between tests.
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
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('Built for close-range combat.')

    const buttons = wrapper.findAll('button')
    const scrap = findButton(wrapper, 'Scrap')
    const sell = findButton(wrapper, 'Sell')

    // The old UTooltip hover description is now a shadcn Tooltip wired to the
    // button: focusing the trigger reveals the tooltip and the trigger gets
    // aria-describedby pointing at it.
    await expectTooltip(scrap, 'Scrap')
    await expectTooltip(sell, 'Sell')

    const actions = buttons.map((button) => button.text())
    expect(actions.indexOf('Sell')).toBeLessThan(actions.indexOf('Scrap'))
  })

  it('includes the junk quantity in the sell-all tooltip on hover', async () => {
    const wrapper = mount(StorageItemCard, {
      props: { item: { name: 'Desk Fan', value: 10 }, itemType: 'junk', count: 3 },
      global: { stubs: { Icon: true } },
    })

    // The single-sell tooltip distinguishes the count>1 case.
    await expectTooltip(findButton(wrapper, 'Sell'), 'Sell one')

    const sellAll = findButton(wrapper, 'Sell all')
    // reka-ui opens on pointermove (not pointerenter); the open is delayed by
    // TooltipProvider's delayDuration (200ms, matching the old UTooltip delay).
    sellAll.element.dispatchEvent(new MouseEvent('pointermove', { bubbles: true }))
    await vi.waitFor(() => {
      const tooltip = document.querySelector<HTMLElement>('[role="tooltip"]')
      expect(tooltip?.textContent).toContain('Sell all (3)')
    })
    expect(sellAll.attributes('aria-describedby')).toBe(
      document.querySelector<HTMLElement>('[role="tooltip"]')?.id
    )
  })

  it('emits the inventory actions on click', async () => {
    const weapon = mount(StorageItemCard, {
      props: {
        item: {
          name: '10mm Pistol',
          rarity: 'rare',
          value: 50,
          weapon_subtype: 'pistol',
        },
        itemType: 'weapon',
      },
      global: { stubs: { Icon: true } },
    })
    await findButton(weapon, 'Scrap').trigger('click')
    expect(weapon.emitted('scrap')).toHaveLength(1)
    await findButton(weapon, 'Sell').trigger('click')
    expect(weapon.emitted('sell')).toHaveLength(1)

    const lunchbox = mount(StorageItemCard, {
      props: { item: { name: 'Lunchbox', value: 500 }, itemType: 'lunchbox' },
      global: { stubs: { Icon: true } },
    })
    await expectTooltip(findButton(lunchbox, 'Open'), 'Open lunchbox')
    await findButton(lunchbox, 'Open').trigger('click')
    expect(lunchbox.emitted('open')).toHaveLength(1)

    const junk = mount(StorageItemCard, {
      props: { item: { name: 'Desk Fan', value: 10 }, itemType: 'junk', count: 3 },
      global: { stubs: { Icon: true } },
    })
    await findButton(junk, 'Sell all').trigger('click')
    expect(junk.emitted('sellAll')).toHaveLength(1)
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
    expect(text).toContain('Intelligence:')
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
