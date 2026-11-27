import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import MapLegend from '@/modules/map/components/MapLegend.vue'
import { PURPOSE_META } from '@/modules/map/models/purposeMeta'

const mountLegend = () => mount(MapLegend, { global: { stubs: { Icon: true } } })

describe('MapLegend', () => {
  it('keys the four purposes the marker bodies encode', () => {
    const text = mountLegend().text()
    for (const entry of PURPOSE_META) {
      expect(text).toContain(entry.label)
      expect(text).toContain(entry.hint)
    }
  })

  it('draws one distinct body shape per purpose', () => {
    const shapes = mountLegend()
      .findAll('svg .legend-shape')
      .map((node) => node.element.tagName.toLowerCase())
    expect(shapes).toEqual(['circle', 'path', 'circle', 'rect'])
  })

  it('retains symbolic states independently of place colours', () => {
    const text = mountLegend().text()
    for (const state of ['Unscouted', 'Cleared', 'Cooldown', 'Exploring'])
      expect(text).toContain(state)
  })

  it('names the three non-place signals', () => {
    const text = mountLegend().text()
    for (const signal of ['Vault signal', 'Expedition site', 'Party / cluster'])
      expect(text).toContain(signal)
  })

  it('no longer keys the five site families', () => {
    const text = mountLegend().text()
    for (const family of ['Civil', 'Industry', 'Threat', 'Knowledge', 'Spectacle'])
      expect(text).not.toContain(family)
  })

  it('keeps the legend to three blocks and one explanatory line', () => {
    const wrapper = mountLegend()
    expect(wrapper.findAll('h3').map((node) => node.text())).toEqual([
      'Purpose',
      'Status',
      'Signals',
    ])
    expect(wrapper.findAll('p')).toHaveLength(1)
  })

  it('names the legend region for assistive technology', () => {
    expect(mountLegend().find('[role="region"]').attributes('aria-label')).toBe('Map legend')
  })

  it('shows the reference without a nested expand control', () => {
    expect(mountLegend().find('button').exists()).toBe(false)
  })
})
