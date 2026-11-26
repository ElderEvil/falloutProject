import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import MapLegend from '@/modules/map/components/MapLegend.vue'
import { MARKER_TYPES } from '@/modules/map/models/markerTypeMeta'
import { FAMILY_LABELS, GROUP_FAMILIES } from '@/modules/map/models/groupColors'

const mountLegend = (props = {}) => mount(MapLegend, { props, global: { stubs: { Icon: true } } })

describe('MapLegend', () => {
  it('retains symbolic states independently of place colors', () => {
    const wrapper = mountLegend()
    for (const state of ['Unscouted', 'Cleared', 'Cooldown', 'Exploring'])
      expect(wrapper.text()).toContain(state)
  })

  it('uses the canonical marker labels', () => {
    const wrapper = mountLegend()
    for (const symbol of MARKER_TYPES) expect(wrapper.text()).toContain(symbol.label)
    expect(wrapper.text()).toContain('Grouped markers')
  })

  it('explains that vault signals are not travel destinations', () => {
    expect(mountLegend().text()).toContain('Vault signals are distant vaults, not destinations')
  })

  it('names the legend region for assistive technology', () => {
    expect(mountLegend().find('[role="region"]').attributes('aria-label')).toBe('Map legend')
  })

  it('shows the full reference without a nested expand control', () => {
    const wrapper = mountLegend()
    expect(wrapper.text()).toContain('Marker symbols')
    expect(wrapper.text()).toContain('Place status')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('keys the five site families instead of listing every place type', () => {
    const wrapper = mountLegend()
    expect(wrapper.text()).toContain('Site families')
    for (const label of Object.values(FAMILY_LABELS)) expect(wrapper.text()).toContain(label)
  })

  it('swatches each family with its own colour and no duplicates', () => {
    const swatches = mountLegend()
      .findAll('circle')
      .map((circle) => circle.attributes('style') ?? '')
      .filter((style) => style.includes('--color-family-'))
    expect(swatches).toHaveLength(5)
    for (const color of Object.values(GROUP_FAMILIES))
      expect(swatches.some((style) => style.includes(color))).toBe(true)
  })

  it('hides the family key when colouring is off', () => {
    expect(mountLegend({ groupColors: false }).text()).not.toContain('Site families')
  })

  it.each([
    ['reads', 'getItem', 'SecurityError', 'Unscouted'],
    ['writes', 'setItem', 'QuotaExceededError', 'Cooldown'],
  ])('works when storage %s are unavailable', (_, method, errorName, fallback) => {
    vi.spyOn(Storage.prototype, method as 'getItem' | 'setItem').mockImplementation(() => {
      throw new DOMException('denied', errorName)
    })
    try {
      expect(mountLegend().text()).toContain(fallback)
    } finally {
      vi.restoreAllMocks()
    }
  })
})
