import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
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

type CardProps = InstanceType<typeof StorageItemCard>['$props']

/** Mounts the card with the required `item`/`itemType` filled; callers override what they need. */
function renderCard(item: CardProps['item'], props: Partial<CardProps> = {}): VueWrapper {
  return mount(StorageItemCard, {
    props: { item, itemType: 'weapon', ...props } as CardProps,
    global: { stubs: { Icon: true } },
  })
}

function findButton(wrapper: VueWrapper, label: string) {
  const found = wrapper.findAll('button').find((button) => button.text().includes(label))
  if (!found) throw new Error(`No button labelled "${label}"`)
  return found
}

function renderedTooltip(): HTMLElement {
  const tooltip = document.querySelector<HTMLElement>('[role="tooltip"]')
  if (!tooltip) throw new Error('No tooltip rendered')
  return tooltip
}

// reka-ui's TooltipTrigger opens on native `focus` (immediate, no delay) and on
// `pointermove` (delayed by TooltipProvider's delayDuration). jsdom's synthetic
// events carry no pointerType, so dispatch real events — the same approach the
// sibling AISettingsPanel.test.ts uses for reka-ui pointer/keyboard behaviour.
const expectTooltip = async (button: ReturnType<typeof findButton>, text: string) => {
  button.element.dispatchEvent(new FocusEvent('focus'))
  await nextTick()
  const tooltip = renderedTooltip()
  expect(tooltip.textContent).toContain(text)
  expect(button.attributes('aria-describedby')).toBe(tooltip.id)
  button.element.dispatchEvent(new FocusEvent('blur'))
  await nextTick()
}

describe('StorageItemCard', () => {
  beforeEach(() => {
    // Tooltip content is teleported to <body>; drop leftovers between tests.
    document.querySelectorAll('[role="tooltip"]').forEach((element) => element.remove())
  })

  it.each(['weapon', 'junk', 'lunchbox', 'pet_carrier'])(
    'disables all %s actions until the refresh finishes',
    async (itemType) => {
      const wrapper = renderCard(
        { name: 'Stored item', value: 10 },
        { itemType, count: 3, disabled: true }
      )

      const buttons = wrapper.findAll('button')
      expect(buttons.length).toBeGreaterThan(0)
      for (const button of buttons) {
        expect(button.attributes('disabled')).toBeDefined()
        await button.trigger('click')
      }
      for (const event of ['sell', 'sellAll', 'scrap', 'open']) {
        expect(wrapper.emitted(event)).toBeUndefined()
      }
      await wrapper.setProps({ disabled: false })
      for (const button of buttons) expect(button.attributes('disabled')).toBeUndefined()
      wrapper.unmount()
    }
  )

  it('offers Open for a pet carrier with a carrier-specific tooltip', async () => {
    const wrapper = renderCard(
      { name: 'Pet Carrier', value: 10 },
      { itemType: 'pet_carrier', count: 1 }
    )

    await expectTooltip(findButton(wrapper, 'Open'), 'Open pet carrier')
    wrapper.unmount()
  })

  it('presents the item description and clearly labelled inventory actions', async () => {
    const wrapper = renderCard({
      name: 'Sawed-off Shotgun',
      description: 'Built for close-range combat.',
      rarity: 'common',
      value: 120,
      weapon_subtype: 'shotgun',
    })

    expect(wrapper.text()).toContain('Built for close-range combat.')

    const scrap = findButton(wrapper, 'Scrap')
    const sell = findButton(wrapper, 'Sell')

    // The old UTooltip hover description is now a shadcn Tooltip wired to the
    // button: focusing the trigger reveals the tooltip and the trigger gets
    // aria-describedby pointing at it.
    await expectTooltip(scrap, 'Scrap')
    await expectTooltip(sell, 'Sell')

    const actions = wrapper.findAll('button').map((button) => button.text())
    expect(actions.indexOf('Sell')).toBeLessThan(actions.indexOf('Scrap'))
  })

  it('includes the junk quantity in the sell-all tooltip on hover', async () => {
    const wrapper = renderCard({ name: 'Desk Fan', value: 10 }, { itemType: 'junk', count: 3 })

    // The single-sell tooltip distinguishes the count>1 case.
    await expectTooltip(findButton(wrapper, 'Sell'), 'Sell one')

    const sellAll = findButton(wrapper, 'Sell all')
    // reka-ui opens on pointermove (not pointerenter); the open is delayed by
    // TooltipProvider's delayDuration (200ms, matching the old UTooltip delay).
    sellAll.element.dispatchEvent(new MouseEvent('pointermove', { bubbles: true }))
    await vi.waitFor(() => {
      expect(renderedTooltip().textContent).toContain('Sell all (3)')
    })
    expect(sellAll.attributes('aria-describedby')).toBe(renderedTooltip().id)
  })

  it('emits the inventory actions on click', async () => {
    const weapon = renderCard({
      name: '10mm Pistol',
      rarity: 'rare',
      value: 50,
      weapon_subtype: 'pistol',
    })
    await findButton(weapon, 'Scrap').trigger('click')
    expect(weapon.emitted('scrap')).toHaveLength(1)
    await findButton(weapon, 'Sell').trigger('click')
    expect(weapon.emitted('sell')).toHaveLength(1)

    const lunchbox = renderCard({ name: 'Lunchbox', value: 500 }, { itemType: 'lunchbox' })
    await expectTooltip(findButton(lunchbox, 'Open'), 'Open lunchbox')
    await findButton(lunchbox, 'Open').trigger('click')
    expect(lunchbox.emitted('open')).toHaveLength(1)

    const junk = renderCard({ name: 'Desk Fan', value: 10 }, { itemType: 'junk', count: 3 })
    await findButton(junk, 'Sell all').trigger('click')
    expect(junk.emitted('sellAll')).toHaveLength(1)
  })

  it('renders the unified weapon stats including accuracy', () => {
    const text = renderCard({
      name: '10mm Pistol',
      rarity: 'rare',
      value: 50,
      weapon_subtype: 'pistol',
      damage_min: 2,
      damage_max: 5,
      stat: 'agility',
      accuracy: 70,
      weapon_type: 'gun',
    }).text()

    expect(text).toContain('Damage:')
    expect(text).toContain('2-5')
    expect(text).toContain('Accuracy:')
    expect(text).toContain('70%')
    expect(text).toContain('Type:')
  })

  it('renders outfit SPECIAL bonuses alongside gender', () => {
    const text = renderCard(
      {
        name: 'Lab Coat',
        rarity: 'rare',
        outfit_type: 'rare_outfit',
        intelligence: 2,
        gender: 'female',
      },
      { itemType: 'outfit' }
    ).text()

    expect(text).toContain('Intelligence:')
    expect(text).toContain('+2')
    expect(text).toContain('Gender:')
    expect(text).toContain('female')
  })

  it('renders generic supplies without inventory actions', () => {
    const wrapper = renderCard(
      { name: 'Nuka-Cola Quantum', rarity: 'rare', value: 50, item_type: 'consumable' },
      { itemType: 'consumable', count: 2 }
    )

    expect(wrapper.text()).toContain('Nuka-Cola Quantum')
    expect(wrapper.text()).toContain('×2')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('renders pet effect stats, omitting zero bonuses', () => {
    const wrapper = renderCard(
      {
        name: 'Dogmeat',
        rarity: 'rare',
        value: 100,
        effect: { strength: 2, max_health: 50, damage_pct: 0.25, luck: 0 },
      },
      { itemType: 'pet' }
    )

    const text = wrapper.text()
    expect(text).toContain('Strength:')
    expect(text).toContain('+2')
    expect(text).toContain('Max HP:')
    expect(text).toContain('+50')
    expect(text).toContain('Damage:')
    expect(text).toContain('+25%')
    expect(text).not.toContain('Luck:')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })
})
