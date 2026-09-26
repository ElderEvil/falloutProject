import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { Icon } from '@iconify/vue'
import MapMarker from '@/modules/map/components/MapMarker.vue'

/**
 * Regression test for invisible markers on the World Map.
 *
 * Bug: the icon lives inside an SVG <foreignObject> which was wrapped in
 * UTooltip's HTML <div>s. In Chromium, a <foreignObject> wrapped inside HTML
 * elements (a <div> between the SVG <g> and the <foreignObject>) collapses to
 * 0x0 and never renders. Markers were present in the DOM but invisible.
 *
 * Fix: <foreignObject> must remain a DIRECT child of the <g> element (no HTML
 * wrapper in between).
 */
describe('MapMarker', () => {
  it('renders foreignObject as a direct child of <g> (no HTML div wrapper)', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Test Location',
        type: 'visited',
      },
      global: {
        stubs: { Icon: true },
      },
    })

    const g = wrapper.find('g.map-marker')
    expect(g.exists()).toBe(true)

    // The <g> must contain the <foreignObject> directly. An HTML <div>
    // (e.g. from a tooltip wrapper) between them breaks Chromium rendering.
    const directChildren = g.element.children
    const hasHtmlDivWrapper = Array.from(directChildren).some(
      (el) => el.tagName.toLowerCase() === 'div'
    )
    expect(hasHtmlDivWrapper).toBe(false)

    // The foreignObject must exist and be reachable directly under <g>
    expect(g.find('foreignObject').exists()).toBe(true)
    expect(g.find('foreignObject').element.parentElement).toBe(g.element)
  })

  it('still exposes the tooltip text via aria-label and native <title>', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 30,
        y: 40,
        name: 'Sunken Church',
        type: 'origin',
      },
      global: {
        stubs: { Icon: true },
      },
    })

    const g = wrapper.find('g.map-marker')
    expect(g.attributes('aria-label')).toBe('Sunken Church (Origin)')
    expect(g.find('title').text()).toBe('Sunken Church (Origin)')
  })

  it('applies marker-locked class and shows "Unknown Location" when is_unlocked is false', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 50,
        y: 60,
        name: 'Hidden Place',
        type: 'discovery',
        is_unlocked: false,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    const g = wrapper.find('g.map-marker')
    expect(g.classes()).toContain('marker-locked')
    expect(g.attributes('aria-label')).toBe('Unknown Location (Discovery)')
    expect(g.find('title').text()).toBe('Unknown Location (Discovery)')
    expect(g.find('.marker-label').text()).toBe('Unknown Location')
  })

  it('does not apply marker-locked to vault types even when is_unlocked is false', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 50,
        y: 60,
        name: 'Vault 101',
        type: 'vault',
        is_unlocked: false,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    const g = wrapper.find('g.map-marker')
    expect(g.classes()).not.toContain('marker-locked')
    expect(g.find('.marker-label').text()).toBe('Vault 101')
  })

  it('pulses an unlocked discovery only while unseen', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Sunken Church',
        type: 'discovery',
        is_unlocked: true,
        unseen: true,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.marker-icon').classes()).toContain('marker-discovery')
  })

  it('stops the pulse once an unseen discovery becomes seen', async () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Sunken Church',
        type: 'discovery',
        is_unlocked: true,
        unseen: true,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.marker-icon').classes()).toContain('marker-discovery')

    await wrapper.setProps({ unseen: false })

    expect(wrapper.find('.marker-icon').classes()).not.toContain('marker-discovery')
  })

  it('never pulses locked discoveries, even while unseen', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Hidden Place',
        type: 'discovery',
        is_unlocked: false,
        unseen: true,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.marker-icon').classes()).not.toContain('marker-discovery')
  })

  it('never pulses non-discovery types, even while unseen', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Old Shack',
        type: 'visited',
        is_unlocked: true,
        unseen: true,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.marker-icon').classes()).not.toContain('marker-discovery')
  })

  it('renders selection as a static ring without pulse animation', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Sunken Church',
        type: 'discovery',
        is_unlocked: true,
        unseen: false,
        selected: true,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.marker-select-ring').exists()).toBe(true)
    expect(wrapper.find('.marker-icon').classes()).not.toContain('marker-discovery')
  })

  it('renders no selection ring when unselected', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Sunken Church',
        type: 'discovery',
        is_unlocked: true,
        unseen: true,
        selected: false,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.marker-select-ring').exists()).toBe(false)
    expect(wrapper.find('.marker-select-ping').exists()).toBe(false)
  })

  it('emits a single ping element on the click transition', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Sunken Church',
        type: 'visited',
        selected: true,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.findAll('.marker-select-ping')).toHaveLength(1)
  })

  describe('Expedition site markers', () => {
    it('renders a custom icon and label override for a site', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Red Rocket Gas Station',
          type: 'expedition_site',
          icon: 'mdi:gas-station',
          label: 'Expedition Site',
        },
        global: {
          stubs: { Icon: true },
        },
      })

      expect(wrapper.findComponent(Icon).props('icon')).toBe('mdi:gas-station')
      expect(wrapper.attributes('aria-label')).toBe('Red Rocket Gas Station (Expedition Site)')
    })

    it('appends the status line to the tooltip', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Red Rocket Gas Station',
          type: 'expedition_site',
          status: 'READY · LVL 5 · 3 ROOMS',
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.attributes('aria-label')).toBe(
        'Red Rocket Gas Station (Expedition Sites) — READY · LVL 5 · 3 ROOMS'
      )
      expect(wrapper.find('title').text()).toContain('READY · LVL 5 · 3 ROOMS')
    })

    it('renders the cleared badge when cleared', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Red Rocket Gas Station',
          type: 'expedition_site',
          cleared: true,
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('.marker-cleared-badge').exists()).toBe(true)
    })

    it('renders no cleared badge when not cleared', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Red Rocket Gas Station',
          type: 'expedition_site',
          cleared: false,
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('.marker-cleared-badge').exists()).toBe(false)
    })
  })

  describe('Explorer tracking', () => {
    it('renders the pulsing exploring ring on a dispatched target', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Rusty Depot',
          type: 'visited',
          exploring: true,
          status: 'Exploring — Ada',
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('.marker-exploring-ring').exists()).toBe(true)
      expect(wrapper.attributes('aria-label')).toContain('Exploring — Ada')
    })

    it('renders no exploring ring when not exploring', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Rusty Depot',
          type: 'visited',
          exploring: false,
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('.marker-exploring-ring').exists()).toBe(false)
    })

    it('renders a non-interactive explorer marker without focus/role semantics', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 42,
          y: 43,
          name: 'Bob',
          type: 'explorer',
          icon: 'mdi:walk',
          label: 'Explorer',
          interactive: false,
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.attributes('tabindex')).toBeUndefined()
      expect(wrapper.attributes('role')).toBeUndefined()
      expect(wrapper.attributes('aria-label')).toBeUndefined()
      expect(wrapper.find('title').text()).toBe('Bob (Explorer)')
    })

    it('does not emit click for a non-interactive marker', async () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 42,
          y: 43,
          name: 'Bob',
          type: 'explorer',
          interactive: false,
        },
        global: { stubs: { Icon: true } },
      })

      await wrapper.trigger('click')
      expect(wrapper.emitted('click')).toBeUndefined()
    })
  })
})
