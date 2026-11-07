import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import AtlasRoads from '@/modules/map/components/AtlasRoads.vue'
import { MIN_ZOOM, WHEEL_STEP } from '@/modules/map/composables/useMapZoomPan'
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

function railSnapshot(): WorldSnapshotRead {
  const world = snapshot()
  world.roads!.segments.push({
    id: 'rail',
    kind: 'railroad',
    points: [
      [10, 10],
      [90, 90],
    ],
  })
  return world
}

describe('AtlasRoads', () => {
  it('draws a distinct railway with sleepers beneath roads and inside the same fog clip', () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: railSnapshot(), explored: new Uint8Array([1, 0, 0, 0]), zoom: 4 },
    })

    const rail = wrapper.find('[data-layer="railroad"]')
    expect(rail.findAll('polyline')).toHaveLength(3)
    const sleepers = rail.find('polyline[stroke-linecap="butt"]')
    expect(sleepers.attributes('stroke-dasharray')).toBe('0.14 0.8')
    expect(sleepers.attributes('points')).toBe('16,16 144,144')
    expect(wrapper.find('g[clip-path]').element.contains(rail.element)).toBe(true)
    expect(wrapper.findAll('g[data-layer]')[0].attributes('data-layer')).toBe('railroad')
  })

  it('draws backend points at the map scale, with highways above narrower country roads', () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array(4).fill(1), zoom: 2 },
    })

    expect(
      wrapper
        .findAll('[data-layer="country"], [data-layer="highway"]')
        .map((layer) => layer.attributes('data-layer'))
    ).toEqual(['country', 'highway'])

    const highway = wrapper.find('[data-layer="highway"]')
    expect(highway.find('polyline').attributes('points')).toBe('16,32 40,56 112,64')
    expect(highway.findAll('[data-role="road"]')[0].attributes('stroke-width')).toBe('0.8')
    expect(
      wrapper
        .find('[data-layer="country"]')
        .findAll('[data-role="road"]')[0]
        .attributes('stroke-width')
    ).toBe('0.36')
    expect(wrapper.attributes('aria-hidden')).toBe('true')
  })

  it('adds pre-war detail only where the zoom supports it', () => {
    const overview = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array(4).fill(1), zoom: 1 },
    })
    expect(overview.find('[data-layer="country"]').exists()).toBe(false)
    expect(overview.findAll('[data-role="highway-dashes"]')).toHaveLength(0)
    expect(overview.findAll('[data-role="route-shield"]')).toHaveLength(0)
    expect(overview.findAll('[data-role="region-label"]')).toHaveLength(0)
    expect(overview.findAll('[data-role="rail-stop"]')).toHaveLength(0)
    expect(overview.find('[data-role="graticule"]').exists()).toBe(true)
    expect(overview.find('[data-layer="highway"]').exists()).toBe(true)

    const detail = mount(AtlasRoads, {
      props: { snapshot: railSnapshot(), explored: new Uint8Array(4).fill(1), zoom: 4 },
    })
    expect(detail.findAll('[data-role="highway-dashes"]')).toHaveLength(1)
    const shields = detail.findAll('[data-role="route-shield"]')
    expect(shields).toHaveLength(1)
    expect(shields[0].attributes('data-route')).toMatch(/^\d+$/)
    expect(detail.findAll('[data-role="rail-stop"]')).toHaveLength(2)
    expect(detail.findAll('[data-role="region-label"]').length).toBeGreaterThanOrEqual(1)
  })

  it('reveals local roads on the first zoom step in from the full atlas', () => {
    const wrapper = mount(AtlasRoads, {
      props: {
        snapshot: snapshot(),
        explored: new Uint8Array(4).fill(1),
        zoom: MIN_ZOOM + WHEEL_STEP,
      },
    })

    const country = wrapper.find('[data-layer="country"]')
    expect(country.exists()).toBe(true)
    expect(country.findAll('[data-role="road"]')[0].attributes('stroke-width')).toBe('0.36')
  })

  it('flattens road paint into one isolated opacity group with opaque strokes', () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: railSnapshot(), explored: new Uint8Array(4).fill(1), zoom: 4 },
    })

    const paint = wrapper.find('[data-role="road-paint"]')
    expect(paint.exists()).toBe(true)
    expect(Number(paint.attributes('opacity'))).toBeLessThan(1)

    const roads = wrapper.findAll('[data-role="road"]')
    expect(roads.length).toBeGreaterThan(0)
    for (const road of roads) {
      expect(paint.element.contains(road.element)).toBe(true)
      expect(road.attributes('opacity')).toBeUndefined()
    }
  })

  it('renders deterministic region stencils at mid zoom only', () => {
    const regions = (zoom: number) =>
      mount(AtlasRoads, {
        props: { snapshot: snapshot(), explored: new Uint8Array(4).fill(1), zoom },
      })
        .findAll('[data-role="region-label"]')
        .map((label) => label.attributes('data-region'))

    const first = regions(2)
    const second = regions(2)
    expect(first.length).toBeGreaterThan(0)
    expect(second).toEqual(first)
    expect(regions(1)).toHaveLength(0)
  })

  it('draws an 11x11 survey graticule inside the fog clip', () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array(4).fill(1), zoom: 2 },
    })

    const graticule = wrapper.find('[data-role="graticule"]')
    expect(graticule.findAll('line')).toHaveLength(22)
    expect(wrapper.find('g[clip-path]').element.contains(graticule.element)).toBe(true)
  })

  it('renders worn segments with a decay overlay at close zoom', () => {
    const world = snapshot()
    world.roads!.segments.push({
      id: 'A',
      kind: 'highway',
      points: [
        [80, 10],
        [90, 20],
      ],
    })

    const far = mount(AtlasRoads, {
      props: { snapshot: world, explored: new Uint8Array(4).fill(1), zoom: 2 },
    })
    expect(far.findAll('[data-role="road-decay"]')).toHaveLength(0)

    const close = mount(AtlasRoads, {
      props: { snapshot: world, explored: new Uint8Array(4).fill(1), zoom: 4 },
    })
    expect(close.findAll('[data-role="road-decay"]')).toHaveLength(1)
  })

  it('clips the whole stroke to explored tiles, updates with fog, and supports the existing fog toggle', async () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array([1, 0, 0, 0]), zoom: 2 },
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
      props: { snapshot: snapshot(), explored: new Uint8Array([1]), zoom: 2 },
    })
    expect(wrapper.find('clipPath path').attributes('d')).toBe('')
    expect(wrapper.find('g[clip-path]').exists()).toBe(true)
  })

  it('removes roads when the snapshot is missing, lacks roads, or belongs to another base', async () => {
    const wrapper = mount(AtlasRoads, {
      props: { snapshot: snapshot(), explored: new Uint8Array(4), zoom: 2 },
    })
    expect(wrapper.findAll('polyline')).toHaveLength(5)
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
