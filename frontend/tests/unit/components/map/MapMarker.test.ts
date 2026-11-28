import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { Icon } from '@iconify/vue'
import MapMarker from '@/modules/map/components/MapMarker.vue'
import { MARKER_GLYPH_SIZE } from '@/modules/map/models/markerTypeMeta'

/**
 * Regression tests for invisible markers on the World Map.
 *
 * The glyph must render natively as `<g class="marker-glyph">` wrapping the
 * Iconify `<svg>`, and dweller art as a clipped SVG `<image>`: a
 * `<foreignObject>` under an HTML parent collapses to 0x0 in Chromium and made
 * fully-rendered markers invisible.
 */
const glyphWidth = `${MARKER_GLYPH_SIZE}px`

function mountMarker(props: Record<string, unknown> = {}) {
  return mount(MapMarker, {
    props: { x: 10, y: 20, name: 'Sunken Church', type: 'origin', ...props },
    global: { stubs: { Icon: true } },
  })
}

describe('MapMarker', () => {
  it('renders the glyph natively in SVG (no <foreignObject> wrapper)', () => {
    const g = mountMarker({ type: 'visited' }).find('g.map-marker')
    expect(g.find('foreignObject').exists()).toBe(false)
    expect(g.find('g.marker-glyph').findComponent(Icon).exists()).toBe(true)
  })

  it('shrinks only the glyph when iconScale is set', () => {
    const wrapper = mountMarker()
    expect(wrapper.findComponent(Icon).props('width')).toBe(glyphWidth)
    expect(wrapper.find('circle.marker-hit-area').attributes('r')).toBe('6')
    expect(wrapper.find('circle.marker-backing').attributes('r')).toBe('4.2')
  })

  it('shrinks disc, rings, portrait and label together when bodyScale is set', () => {
    const wrapper = mountMarker({
      bodyScale: 0.72,
      selected: true,
      exploring: true,
    })
    // Body and glyph follow the factor together, and the hit area stays full, so
    // a smaller marker never costs an easier click.
    expect(wrapper.find('circle.marker-backing').attributes('r')).toBe('3.024')
    expect(wrapper.find('circle.marker-select-ring').attributes('r')).toBe('2.232')
    expect(wrapper.find('circle.marker-exploring-ring').attributes('r')).toBe('2.232')
    expect(wrapper.find('circle.marker-hit-area').attributes('r')).toBe('6')
    expect(wrapper.findComponent(Icon).props('width')).toBe(`${MARKER_GLYPH_SIZE * 0.72}px`)
    const label = wrapper.find('text.marker-label')
    expect(label.attributes('y')).toBe('-2.448')
    expect(label.attributes('style')).toContain('font-size: 1.728px')
  })

  it('renders a transparent hit area and a dark backing disc beneath the glyph', () => {
    const g = mountMarker().find('g.map-marker')
    const hit = g.find('circle.marker-hit-area')
    expect(hit.attributes('r')).toBe('6')
    expect(hit.attributes('fill')).toBe('transparent')

    const backing = g.find('circle.marker-backing')
    expect(backing.attributes('r')).toBe('4.2')
    const children = Array.from(g.element.children)
    expect(children.indexOf(backing.element)).toBeLessThan(
      children.indexOf(g.find('g.marker-glyph').element)
    )
  })

  it('still exposes the tooltip text via aria-label and native <title>', () => {
    const wrapper = mountMarker()
    expect(wrapper.attributes('aria-label')).toBe('Sunken Church (Origin)')
    expect(wrapper.find('title').text()).toBe('Sunken Church (Origin)')
  })

  it('applies marker-locked class and shows "Unknown Location" when is_unlocked is false', () => {
    const wrapper = mountMarker({ name: 'Hidden Place', type: 'discovery', is_unlocked: false })
    expect(wrapper.find('g.map-marker').classes()).toContain('marker-locked')
    expect(wrapper.attributes('aria-label')).toBe('Unknown Location (Discovery)')
    expect(wrapper.find('title').text()).toBe('Unknown Location (Discovery)')
    expect(wrapper.find('.marker-label').text()).toBe('Unknown Location')
  })

  it('does not apply marker-locked to vault types even when is_unlocked is false', () => {
    const wrapper = mountMarker({ name: 'Vault 101', type: 'vault', is_unlocked: false })
    expect(wrapper.classes()).not.toContain('marker-locked')
    expect(wrapper.find('.marker-label').text()).toBe('Vault 101')
  })

  it.each([
    ['an unlocked unseen discovery', { type: 'discovery', is_unlocked: true, unseen: true }, true],
    ['a locked discovery', { type: 'discovery', is_unlocked: false, unseen: true }, false],
    ['a non-discovery', { type: 'visited', is_unlocked: true, unseen: true }, false],
  ])('pulses %s only while it qualifies', (_, props, pulses) => {
    const classes = mountMarker(props).find('g.marker-glyph').classes()
    expect(classes.includes('marker-discovery')).toBe(pulses)
  })

  it('stops the pulse once an unseen discovery becomes seen', async () => {
    const wrapper = mountMarker({ type: 'discovery', is_unlocked: true, unseen: true })
    expect(wrapper.find('g.marker-glyph').classes()).toContain('marker-discovery')

    await wrapper.setProps({ unseen: false })

    expect(wrapper.find('g.marker-glyph').classes()).not.toContain('marker-discovery')
  })

  it.each([true, false])('renders selection as a static ring only when selected=%s', (selected) => {
    const wrapper = mountMarker({
      type: 'discovery',
      is_unlocked: true,
      unseen: !selected,
      selected,
    })
    expect(wrapper.find('.marker-select-ring').exists()).toBe(selected)
    if (selected) {
      expect(wrapper.find('g.marker-glyph').classes()).not.toContain('marker-discovery')
    } else {
      expect(wrapper.find('.marker-select-ping').exists()).toBe(false)
    }
  })

  it('emits a single ping element on the click transition', () => {
    expect(
      mountMarker({ type: 'visited', selected: true }).findAll('.marker-select-ping')
    ).toHaveLength(1)
  })

  describe('Expedition site markers', () => {
    it('renders a custom icon and label override for a site', () => {
      const wrapper = mountMarker({
        name: 'Red Rocket Gas Station',
        type: 'expedition_site',
        icon: 'mdi:gas-station',
        label: 'Expedition Site',
      })
      expect(wrapper.findComponent(Icon).props('icon')).toBe('mdi:gas-station')
      expect(wrapper.attributes('aria-label')).toBe('Red Rocket Gas Station (Expedition Site)')
    })

    it('appends the status line to the tooltip', () => {
      const wrapper = mountMarker({
        name: 'Red Rocket Gas Station',
        type: 'expedition_site',
        status: 'READY · LVL 5 · 3 ROOMS',
      })
      expect(wrapper.attributes('aria-label')).toBe(
        'Red Rocket Gas Station (Expedition Sites) — READY · LVL 5 · 3 ROOMS'
      )
      expect(wrapper.find('title').text()).toContain('READY · LVL 5 · 3 ROOMS')
    })

    it.each([
      [true, true],
      [false, false],
    ])('renders the cleared badge only when cleared=%s', (cleared, shown) => {
      const wrapper = mountMarker({
        name: 'Red Rocket Gas Station',
        type: 'expedition_site',
        cleared,
      })
      expect(wrapper.find('.marker-cleared-badge').exists()).toBe(shown)
    })
  })

  describe('Explorer tracking', () => {
    it.each([
      [true, true],
      [false, false],
    ])('renders the exploring ring only when exploring=%s', (exploring, shown) => {
      const wrapper = mountMarker({
        name: 'Rusty Depot',
        type: 'visited',
        exploring,
        status: 'Exploring — Ada',
      })
      expect(wrapper.find('.marker-exploring-ring').exists()).toBe(shown)
      if (exploring) expect(wrapper.attributes('aria-label')).toContain('Exploring — Ada')
    })

    it('renders a non-interactive explorer marker without focus/role semantics', () => {
      const wrapper = mountMarker({
        x: 42,
        y: 43,
        name: 'Bob',
        type: 'explorer',
        icon: 'mdi:walk',
        label: 'Explorer',
        interactive: false,
      })
      expect(wrapper.attributes('tabindex')).toBeUndefined()
      expect(wrapper.attributes('role')).toBeUndefined()
      expect(wrapper.attributes('aria-label')).toBeUndefined()
      expect(wrapper.find('title').text()).toBe('Bob (Explorer)')
    })

    it('does not emit click for a non-interactive marker', async () => {
      const wrapper = mountMarker({
        x: 42,
        y: 43,
        name: 'Bob',
        type: 'explorer',
        interactive: false,
      })
      await wrapper.trigger('click')
      expect(wrapper.emitted('click')).toBeUndefined()
    })
  })

  describe('Marker art (portrait image)', () => {
    it('renders a clipped SVG <image> in place of the glyph when art is present', () => {
      const wrapper = mountMarker({
        name: 'Bob',
        type: 'explorer',
        icon: 'mdi:walk',
        artSrc: 'https://cdn.example/bob.png',
      })
      const image = wrapper.find('g.map-marker image')
      expect(image.attributes('href')).toBe('https://cdn.example/bob.png')
      // A circular clip keeps the thumbnail inside the marker disc.
      expect(image.attributes('clip-path')).toMatch(/^url\(#.+\)$/)
      // The portrait replaces the icon glyph rather than stacking over it.
      expect(wrapper.find('g.marker-glyph').exists()).toBe(false)
    })

    it('focuses the top of the portrait so thumbnails show the head', () => {
      const image = mountMarker({
        name: 'Bob',
        type: 'explorer',
        icon: 'mdi:walk',
        artSrc: 'https://cdn.example/bob.png',
      }).find('g.map-marker image').element.outerHTML
      // Matches DwellerPortrait's head focus; centering crops full-body portraits.
      expect(image).toContain('xMidYMin slice')
      expect(image).not.toContain('xMidYMid')
    })

    it.each([
      ['an absolute URL', 'https://cdn.example/bob.png', 'https://cdn.example/bob.png'],
      [
        'backend-static art',
        '/static/portraits/bob.png',
        'http://localhost:8000/static/portraits/bob.png',
      ],
      ['location data-URL art', 'data:image/png;base64,art', 'data:image/png;base64,art'],
    ])('resolves %s to a usable href', (_, artSrc, href) => {
      const wrapper = mountMarker({ name: 'Bob', type: 'explorer', icon: 'mdi:walk', artSrc })
      expect(wrapper.find('g.map-marker image').attributes('href')).toBe(href)
    })

    it('renders the marker icon when no art is present', () => {
      const wrapper = mountMarker({ name: 'Old Shack', type: 'visited', icon: 'mdi:cave' })
      expect(wrapper.find('g.map-marker image').exists()).toBe(false)
      expect(wrapper.findComponent(Icon).props('icon')).toBe('mdi:cave')
    })

    it('keeps the icon fallback for locked markers despite art', () => {
      const wrapper = mountMarker({
        name: 'Hidden Place',
        type: 'discovery',
        is_unlocked: false,
        artSrc: 'https://cdn.example/hidden.png',
      })
      expect(wrapper.find('g.map-marker image').exists()).toBe(false)
      // Identity survives being unscouted: the archetype glyph stays, dimmed
      // inside a dashed ring, instead of being replaced by a "?" marker.
      expect(wrapper.findComponent(Icon).props('icon')).toBe('mdi:map-marker-question')
      expect(wrapper.classes()).toContain('marker-locked')
    })

    it('swaps to the marker icon fallback when art fails to load', async () => {
      const wrapper = mountMarker({
        name: 'Bob',
        type: 'explorer',
        icon: 'mdi:walk',
        artSrc: 'https://cdn.example/bob.png',
      })
      await wrapper.find('g.map-marker image').trigger('error')

      expect(wrapper.find('g.map-marker image').exists()).toBe(false)
      const glyph = wrapper.find('g.marker-glyph')
      expect(glyph.findComponent(Icon).props('icon')).toBe('mdi:walk')
    })
  })

  describe('Danger ramp', () => {
    it('labels catalog danger without adding a risk color', () => {
      const wrapper = mountMarker({ name: 'Raider Camp', type: 'visited', risk: 'high' })
      expect(wrapper.find('g.map-marker.marker-risk-high').exists()).toBe(false)
      expect(wrapper.attributes('aria-label')).toContain('High risk')
      expect(wrapper.find('circle.marker-backing').exists()).toBe(true)
    })

    it('falls back to the base difficulty band when the risk is missing', () => {
      const wrapper = mountMarker({ name: 'Gas Station', type: 'visited', baseDifficulty: 3 })
      expect(wrapper.find('g.map-marker.marker-risk-medium').exists()).toBe(false)
      expect(wrapper.attributes('aria-label')).toContain('Medium risk')
    })

    it.each([
      ['without catalog risk data', { name: 'Old Shack', type: 'visited' }],
      [
        'for a locked location',
        { name: 'Hidden Camp', type: 'discovery', is_unlocked: false, risk: 'high' },
      ],
    ])('keeps the neutral ramp %s', (_, props) => {
      const wrapper = mountMarker(props)
      expect(wrapper.find('g.map-marker.marker-risk-medium').exists()).toBe(false)
      expect(wrapper.find('g.map-marker.marker-risk-high').exists()).toBe(false)
      expect(wrapper.attributes('aria-label')).not.toContain('High risk')
    })
  })
})

describe('MapMarker zoom compensation', () => {
  it('uses place-group color only for known places, keeping risk as text', async () => {
    const wrapper = mountMarker({
      x: 20,
      y: 30,
      name: 'Camp',
      type: 'discovery',
      color: 'var(--color-family-threat)',
      risk: 'high',
    })
    expect(wrapper.find('.marker-glyph').attributes('style')).toContain(
      'var(--color-family-threat)'
    )
    expect(wrapper.attributes('aria-label')).toContain('High risk')
    await wrapper.setProps({ is_unlocked: false })
    expect(wrapper.find('.marker-glyph').attributes('style')).toContain(
      'var(--color-theme-primary)'
    )
    expect(wrapper.attributes('aria-label')).not.toContain('High risk')
  })

  it('uses a clock badge and readable cooldown status', () => {
    const wrapper = mountMarker({
      x: 20,
      y: 30,
      name: 'Depot',
      type: 'visited',
      cleared: true,
      cooldown: true,
    })
    expect(wrapper.find('.marker-cooldown-badge').exists()).toBe(true)
    expect(wrapper.find('.marker-cleared-badge').exists()).toBe(false)
    expect(wrapper.attributes('aria-label')).toContain('Cooldown')
  })

  it('scales around its coordinate without shifting the location', () => {
    const wrapper = mountMarker({ x: 20, y: 30, name: 'Depot', type: 'visited', scale: 0.5 })
    expect(wrapper.find('g.map-marker').attributes('transform')).toBe(
      'translate(20, 30) scale(0.5)'
    )
  })

  describe('body shapes', () => {
    it('keeps the plain disc when a marker has no shape', () => {
      const wrapper = mountMarker()
      expect(wrapper.find('circle.marker-backing').exists()).toBe(true)
      expect(wrapper.find('path.marker-backing').exists()).toBe(false)
    })

    it.each([
      ['circle', 'circle'],
      ['diamond', 'path'],
      ['hexagon', 'path'],
      ['square', 'rect'],
    ])('draws %s as a %s body', (shape, tag) => {
      const wrapper = mountMarker({ shape })
      expect(wrapper.find(`${tag}.marker-backing`).exists()).toBe(true)
      const others = ['circle', 'path', 'rect'].filter((t) => t !== tag)
      for (const other of others)
        expect(wrapper.find(`${other}.marker-backing`).exists()).toBe(false)
    })

    it('opens the body for Look places so they never read as a raid target', () => {
      expect(mountMarker({ shape: 'square' }).find('.marker-backing-open').exists()).toBe(true)
      expect(mountMarker({ shape: 'circle' }).find('.marker-backing-open').exists()).toBe(false)
      expect(mountMarker({ shape: 'diamond' }).find('.marker-backing-open').exists()).toBe(false)
      expect(mountMarker({ shape: 'hexagon' }).find('.marker-backing-open').exists()).toBe(false)
    })

    it('resolves an invalid shape to Look, never a filled circle', () => {
      const wrapper = mountMarker({ shape: 'bogus' })
      expect(wrapper.find('rect.marker-backing.marker-backing-open').exists()).toBe(true)
      expect(wrapper.attributes('aria-label')).toContain('Look')
    })

    it('keeps the diamond body inside the disc footprint', () => {
      const d = mountMarker({ shape: 'diamond' }).find('path.marker-backing').attributes('d') ?? ''
      expect(d).toBe('M 0 -4.2 L 4.2 0 L 0 4.2 L -4.2 0 Z')
    })

    it('draws the home hexagon to the disc footprint', () => {
      const d = mountMarker({ shape: 'hexagon' }).find('path.marker-backing').attributes('d') ?? ''
      // Six points, apex up, 1.1x radius: a hexagon holds ~83% of a disc's area at
      // equal circumradius, so 1.1x restores the footprint, and every vertex still
      // sits inside the r=6 hit area.
      expect(d).toBe('M 0 -4.62 L 4.001 -2.31 L 4.001 2.31 L 0 4.62 L -4.001 2.31 L -4.001 -2.31 Z')
      expect(d.trim().endsWith('Z')).toBe(true)
      const ys = [...d.matchAll(/[ML] (-?[\d.]+) (-?[\d.]+)/g)].flatMap((m) => [
        Math.abs(Number(m[2])),
      ])
      expect(Math.max(...ys)).toBeLessThan(6)
      expect(ys.filter((y) => y === 0)).toHaveLength(0)
    })

    it('names the purpose in the accessible label', () => {
      expect(mountMarker({ shape: 'diamond' }).attributes('aria-label')).toContain('Trade')
      expect(mountMarker({ shape: 'circle' }).attributes('aria-label')).toContain('Clear')
      expect(mountMarker({ shape: 'hexagon' }).attributes('aria-label')).toContain('Home')
      expect(mountMarker({ shape: 'square' }).attributes('aria-label')).toContain('Look')
    })

    it('leaves the hit area the same size whatever the shape', () => {
      for (const shape of ['circle', 'diamond', 'hexagon', 'square'])
        expect(mountMarker({ shape }).find('circle.marker-hit-area').attributes('r')).toBe('6')
    })
  })
})

describe('MapMarker purpose-first state', () => {
  const factory = { name: 'Factory', type: 'visited', shape: 'square', icon: 'mdi:factory' }

  it('keeps the body path identical when selection toggles', () => {
    const plain = mountMarker(factory)
    const selected = mountMarker({ ...factory, selected: true })
    expect(selected.find('.marker-backing').attributes()).toEqual(
      plain.find('.marker-backing').attributes()
    )
  })

  it('withholds the archetype glyph behind ? until scouted', () => {
    const wrapper = mountMarker({ ...factory, is_unlocked: false, risk: 'medium' })
    expect(wrapper.findComponent(Icon).props('icon')).toBe('mdi:map-marker-question')
    expect(wrapper.attributes('aria-label')).toBe('Unscouted · Look site · risk unknown')
  })

  it('reads purpose, archetype, risk and state once revealed', () => {
    const wrapper = mountMarker({
      ...factory,
      name: 'Corvega Assembly Plant',
      archetype: 'Factory',
      risk: 'medium',
      status: 'Party en route',
    })
    expect(wrapper.attributes('aria-label')).toBe('Look · Factory · Medium risk · Party en route')
  })

  it('shows a salvage crate badge without redrawing the body', () => {
    const salvage = mountMarker({ ...factory, salvage: true })
    expect(salvage.find('.marker-salvage-badge').exists()).toBe(true)
    expect(salvage.find('.marker-backing').attributes()).toEqual(
      mountMarker(factory).find('.marker-backing').attributes()
    )
  })

  it('announces salvage and keeps status alongside a cleared state', () => {
    expect(
      mountMarker({ ...factory, salvage: true, status: 'Party en route' }).attributes('aria-label')
    ).toContain('Salvage available')

    const cleared = mountMarker({
      name: 'Red Rocket',
      type: 'expedition_site',
      cleared: true,
      status: 'READY · LVL 5 · 3 ROOMS',
    })
    expect(cleared.attributes('aria-label')).toContain('Cleared')
    expect(cleared.attributes('aria-label')).toContain('READY · LVL 5 · 3 ROOMS')
  })
})
