import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import AtlasRoads from '@/modules/map/components/AtlasRoads.vue'
import type { WorldSnapshotRead } from '@/modules/map/models/map'

function snapshot(): WorldSnapshotRead {
  return {
    world_id: 'atlas',
    generator_version: 1,
    recipe_fingerprint: 'recipe',
    snapshot_checksum: 'base',
    width: 2,
    height: 2,
    terrain: ['wasteland', 'wasteland', 'wasteland', 'water'],
    slots: [],
    roads: {
      version: 1,
      base_checksum: 'base',
      checksum: 'roads',
      segments: [
        {
          id: 'h',
          kind: 'highway',
          points: [
            [10, 20],
            [25, 35],
            [70, 40],
          ],
        },
        {
          id: 'c',
          kind: 'country',
          points: [
            [25, 35],
            [30, 60],
          ],
        },
      ],
    },
  }
}

describe('AtlasRoads', () => {
  it('draws a distinct railway with sleepers beneath roads and inside the same fog clip', () => {
    const world = snapshot()
    world.roads!.segments.push({
      id: 'rail',
      kind: 'railroad',
      points: [
        [10, 10],
        [90, 90],
      ],
    })
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: world, explored: new Uint8Array([1, 0, 0, 0]) },
    })
    const rail = wrapper.find('.atlas-road-railroad')
    expect(rail.findAll('polyline')).toHaveLength(3)
    const sleepers = rail.find('polyline[stroke-linecap="butt"]')
    expect(sleepers.classes()).toContain('[stroke-dasharray:0.14_0.8]')
    expect(sleepers.attributes('points')).toBe('16,16 144,144')
    expect(wrapper.find('g[clip-path]').element.contains(rail.element)).toBe(true)
    expect(wrapper.findAll('g[class^="atlas-road-"]')[0].attributes('class')).toBe(
      'atlas-road-railroad'
    )
  })

  it('draws backend points at the map scale, with highways above narrower country roads', () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array(4).fill(1) },
    })
    expect(
      wrapper
        .findAll('.atlas-road-country, .atlas-road-highway')
        .map((layer) => layer.attributes('class'))
    ).toEqual(['atlas-road-country', 'atlas-road-highway'])
    const highway = wrapper.find('.atlas-road-highway')
    expect(highway.find('polyline').attributes('points')).toBe('16,32 40,56 112,64')
    expect(highway.findAll('polyline')[1].classes()).toContain('[stroke-width:0.8]')
    expect(wrapper.find('.atlas-road-country').findAll('polyline')[1].classes()).toContain(
      '[stroke-width:0.36]'
    )
    expect(wrapper.classes()).toContain('pointer-events-none')
  })

  it('clips the whole stroke to explored tiles, updates with fog, and supports the existing fog toggle', async () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array([1, 0, 0, 0]) },
    })
    expect(wrapper.find('clipPath path').attributes('d')).toBe('M0 0h80v80H0Z')
    expect(wrapper.find('g[clip-path]').attributes('clip-path')).toContain(
      wrapper.find('clipPath').attributes('id')
    )
    await wrapper.setProps({ explored: new Uint8Array([1, 1, 0, 0]) })
    expect(wrapper.find('clipPath path').attributes('d')).toBe('M0 0h160v80H0Z')
    await wrapper.setProps({ explored: new Uint8Array(4) })
    expect(wrapper.find('clipPath path').attributes('d')).toBe('')
    await wrapper.setProps({ fogDisabled: true })
    expect(wrapper.find('g[clip-path]').exists()).toBe(false)
  })

  it('fails closed on a mismatched explored mask', () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array([1]) },
    })
    expect(wrapper.find('clipPath path').attributes('d')).toBe('')
    expect(wrapper.find('g[clip-path]').exists()).toBe(true)
  })

  it('removes roads when the snapshot is missing, lacks roads, or belongs to another base', async () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array(4) },
    })
    expect(wrapper.findAll('polyline')).toHaveLength(4)
    const stale = snapshot()
    stale.snapshot_checksum = 'different-base'
    await wrapper.setProps({ snapshot: stale })
    expect(wrapper.findAll('polyline')).toHaveLength(0)
    await wrapper.setProps({ snapshot: { ...snapshot(), roads: null } })
    expect(wrapper.findAll('polyline')).toHaveLength(0)
    await wrapper.setProps({ snapshot: null })
    expect(wrapper.findAll('polyline')).toHaveLength(0)
  })
})
