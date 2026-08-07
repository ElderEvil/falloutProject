import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
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
})
