import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MapClusterMarker from '@/modules/map/components/MapClusterMarker.vue'

describe('MapClusterMarker', () => {
  it('renders a single accessible badge showing the member count', () => {
    const wrapper = mount(MapClusterMarker, { props: { x: 30, y: 40, count: 5 } })

    const badge = wrapper.find('.map-cluster')
    expect(badge.exists()).toBe(true)
    expect(badge.attributes('transform')).toBe('translate(30, 40)')
    expect(badge.attributes('role')).toBe('button')
    expect(badge.attributes('aria-label')).toBe('Zoom in — 5 nearby discoveries')
    expect(badge.text()).toContain('×5')
    expect(badge.find('title').text()).toBe('Zoom in — 5 nearby discoveries')
  })

  it('emits click on pointer activation', async () => {
    const wrapper = mount(MapClusterMarker, { props: { x: 0, y: 0, count: 2 } })

    await wrapper.find('.map-cluster').trigger('click')

    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('emits click on Enter and Space keyboard activation', async () => {
    const wrapper = mount(MapClusterMarker, { props: { x: 0, y: 0, count: 2 } })
    const badge = wrapper.find('.map-cluster')

    await badge.trigger('keydown', { key: 'Enter' })
    await badge.trigger('keydown', { key: ' ' })

    expect(wrapper.emitted('click')).toHaveLength(2)
  })
})
