import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { Icon } from '@iconify/vue'
import MapMarker from '@/modules/map/components/MapMarker.vue'

/**
 * Regression tests for invisible markers on the World Map.
 *
 * Bug: the icon rendered inside an SVG <foreignObject> wrapped in HTML <div>s.
 * In Chromium a <foreignObject> nested under an HTML element collapses to 0x0,
 * so markers were present in the DOM but invisible.
 *
 * Fix: the glyph renders natively as a <g class="marker-glyph"> wrapping the
 * Iconify <svg>, and dweller art as a clipped SVG <image>; no <foreignObject>.
 */
describe('MapMarker', () => {
  it('renders the glyph natively in SVG (no <foreignObject> wrapper)', () => {
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

    // No foreignObject: the icon must stay a native SVG <svg>.
    expect(g.find('foreignObject').exists()).toBe(false)

    const glyph = g.find('g.marker-glyph')
    expect(glyph.exists()).toBe(true)
    expect(glyph.findComponent(Icon).exists()).toBe(true)
  })

  it('renders an enlarged transparent hit area beneath the icon', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Sunken Church',
        type: 'origin',
      },
    })

    const g = wrapper.find('g.map-marker')
    const hit = g.find('circle.marker-hit-area')
    expect(hit.exists()).toBe(true)
    expect(hit.attributes('r')).toBe('6')
    expect(hit.attributes('fill')).toBe('transparent')
  })

  it('renders a uniform dark backing disc directly beneath the glyph', () => {
    const wrapper = mount(MapMarker, {
      props: {
        x: 10,
        y: 20,
        name: 'Sunken Church',
        type: 'origin',
      },
      global: {
        stubs: { Icon: true },
      },
    })

    const g = wrapper.find('g.map-marker')
    const backing = g.find('circle.marker-backing')
    expect(backing.exists()).toBe(true)
    expect(backing.attributes('r')).toBe('3.8')

    const children = Array.from(g.element.children)
    expect(children.indexOf(backing.element)).toBeLessThan(
      children.indexOf(g.find('g.marker-glyph').element)
    )
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

    expect(wrapper.find('g.marker-glyph').classes()).toContain('marker-discovery')
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

    expect(wrapper.find('g.marker-glyph').classes()).toContain('marker-discovery')

    await wrapper.setProps({ unseen: false })

    expect(wrapper.find('g.marker-glyph').classes()).not.toContain('marker-discovery')
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

    expect(wrapper.find('g.marker-glyph').classes()).not.toContain('marker-discovery')
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

    expect(wrapper.find('g.marker-glyph').classes()).not.toContain('marker-discovery')
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
    expect(wrapper.find('g.marker-glyph').classes()).not.toContain('marker-discovery')
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

  describe('Marker art (portrait image)', () => {
    it('renders a clipped SVG <image> when art is present', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Bob',
          type: 'explorer',
          icon: 'mdi:walk',
          artSrc: 'https://cdn.example/bob.png',
        },
        global: { stubs: { Icon: true } },
      })

      const image = wrapper.find('g.map-marker image')
      expect(image.exists()).toBe(true)
      expect(image.attributes('href')).toBe('https://cdn.example/bob.png')
      // A circular clip keeps the thumbnail inside the marker disc.
      expect(image.attributes('clip-path')).toMatch(/^url\(#.+\)$/)
      // The portrait replaces the icon glyph rather than stacking over it.
      expect(wrapper.find('g.marker-glyph').exists()).toBe(false)
    })

    it('focuses the top of the portrait so thumbnails show the head', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Bob',
          type: 'explorer',
          icon: 'mdi:walk',
          artSrc: 'https://cdn.example/bob.png',
        },
        global: { stubs: { Icon: true } },
      })

      // Matches DwellerPortrait's head focus; centering crops full-body portraits.
      const image = wrapper.find('g.map-marker image').element.outerHTML
      expect(image).toContain('xMidYMin slice')
      expect(image).not.toContain('xMidYMid')
    })

    it('resolves backend-static art against the API origin', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Bob',
          type: 'explorer',
          icon: 'mdi:walk',
          artSrc: '/static/portraits/bob.png',
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('g.map-marker image').attributes('href')).toBe(
        'http://localhost:8000/static/portraits/bob.png'
      )
    })

    it('keeps location data-URL art working', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Gas Station',
          type: 'visited',
          artSrc: 'data:image/png;base64,art',
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('g.map-marker image').attributes('href')).toBe('data:image/png;base64,art')
    })

    it('renders the marker icon when no art is present', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Old Shack',
          type: 'visited',
          icon: 'mdi:cave',
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('g.map-marker image').exists()).toBe(false)
      expect(wrapper.findComponent(Icon).props('icon')).toBe('mdi:cave')
    })

    it('keeps the icon fallback for locked markers despite art', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Hidden Place',
          type: 'discovery',
          is_unlocked: false,
          artSrc: 'https://cdn.example/hidden.png',
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('g.map-marker image').exists()).toBe(false)
      expect(wrapper.findComponent(Icon).props('icon')).toBe('mdi:lock-question')
    })

    it('swaps to the marker icon fallback when art fails to load', async () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Bob',
          type: 'explorer',
          icon: 'mdi:walk',
          artSrc: 'https://cdn.example/bob.png',
        },
        global: { stubs: { Icon: true } },
      })

      await wrapper.find('g.map-marker image').trigger('error')

      expect(wrapper.find('g.map-marker image').exists()).toBe(false)
      const glyph = wrapper.find('g.marker-glyph')
      expect(glyph.exists()).toBe(true)
      expect(glyph.findComponent(Icon).props('icon')).toBe('mdi:walk')
    })
  })

  describe('Danger ramp', () => {
    it('ramps the marker to the catalog risk class over a chunky disc', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Raider Camp',
          type: 'visited',
          risk: 'high',
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('g.map-marker.marker-risk-high').exists()).toBe(true)
      expect(wrapper.find('circle.marker-disc').exists()).toBe(true)
    })

    it('falls back to the base difficulty band when the risk is missing', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Gas Station',
          type: 'visited',
          baseDifficulty: 3,
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('g.map-marker.marker-risk-medium').exists()).toBe(true)
    })

    it('keeps the neutral ramp for a marker without catalog risk data', () => {
      const wrapper = mount(MapMarker, {
        props: { x: 10, y: 20, name: 'Old Shack', type: 'visited' },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('g.map-marker.marker-risk-medium').exists()).toBe(false)
      expect(wrapper.find('g.map-marker.marker-risk-high').exists()).toBe(false)
    })

    it('does not leak risk styling for a locked location', () => {
      const wrapper = mount(MapMarker, {
        props: {
          x: 10,
          y: 20,
          name: 'Hidden Camp',
          type: 'discovery',
          is_unlocked: false,
          risk: 'high',
        },
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.find('g.map-marker.marker-risk-high').exists()).toBe(false)
      expect(wrapper.find('.marker-locked').exists()).toBe(true)
    })
  })
})
