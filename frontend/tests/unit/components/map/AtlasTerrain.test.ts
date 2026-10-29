import { describe, expect, it, beforeEach, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import AtlasTerrain from '@/modules/map/components/AtlasTerrain.vue'
import { useMapStore } from '@/modules/map/stores/map'

describe('AtlasTerrain', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  // Minimal canvas stub: blending/dither are cosmetic, so tests assert only that
  // the terrain image renders and is stable — not the rasterisation strategy.
  function stubCanvas() {
    const ctx = {
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 0,
      lineJoin: 'miter',
      lineCap: 'butt',
      setLineDash: vi.fn(),
      save: vi.fn(),
      restore: vi.fn(),
      filter: 'none',
      imageSmoothingEnabled: false,
      imageSmoothingQuality: 'low',
      fillRect: vi.fn(),
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      drawImage: vi.fn(),
      getImageData: vi.fn((_x: number, _y: number, w: number, h: number) => ({
        data: new Uint8ClampedArray(w * h * 4),
      })),
      putImageData: vi.fn(),
    }
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx as any)
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,x')
    return ctx
  }

  // The component reads mask colors from design tokens; jsdom has no stylesheet,
  // so supply the token values the canvas would resolve in the browser.
  function stubMaskTokens() {
    const tokens: Record<string, string> = {
      '--color-terrain-road': '#e6c886',
      '--color-terrain-road-casing': '#241f12',
      '--color-road-highway': '#34342f',
      '--color-road-highway-casing': '#0d0d0b',
      '--color-road-highway-marking': '#d9c48a',
      '--color-terrain-water': '#253440',
    }
    vi.spyOn(window, 'getComputedStyle').mockImplementation(
      () => ({ getPropertyValue: (name: string) => tokens[name] ?? '' }) as CSSStyleDeclaration,
    )
  }

  function snapshot(terrain: string[]) {
    return {
      world_id: 'wasteland-atlas',
      generator_version: 1,
      recipe_fingerprint: 'fp',
      snapshot_checksum: 'cs',
      width: 4,
      height: 4,
      terrain,
      slots: [],
    } as any
  }

  it('renders the terrain image for a snapshot', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot([
      'water',
      'forest',
      'hills',
      'ruins',
      ...new Array(12).fill('wasteland'),
    ])
    stubCanvas()

    const wrapper = mount(AtlasTerrain)
    await flushPromises()

    expect(wrapper.find('image').exists()).toBe(true)
  })

  it('paints road and river masks over the upscaled terrain', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot(new Array(16).fill('wasteland'))
    const ctx = stubCanvas()
    stubMaskTokens()

    mount(AtlasTerrain, { props: { roads: [0], rivers: [15] } })
    await flushPromises()

    // 16 terrain cells + one river rect + one road casing + one road fill.
    expect(ctx.fillRect).toHaveBeenCalledTimes(19)
  })

  it('paints no mask rects without roads or rivers', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot(new Array(16).fill('wasteland'))
    const ctx = stubCanvas()

    mount(AtlasTerrain)
    await flushPromises()

    expect(ctx.fillRect).toHaveBeenCalledTimes(16)
  })

  it('renders no terrain without a snapshot', async () => {
    const store = useMapStore()
    store.worldSnapshot = null
    stubCanvas()

    const wrapper = mount(AtlasTerrain)
    await flushPromises()

    expect(wrapper.find('image').exists()).toBe(false)
    expect(wrapper.findAll('path')).toHaveLength(0)
  })

  it('renders an explicit preview snapshot without replacing the live store', async () => {
    const store = useMapStore()
    store.worldSnapshot = null
    stubCanvas()
    const wrapper = mount(AtlasTerrain, {
      props: { snapshot: snapshot(new Array(16).fill('forest')) },
    })
    await flushPromises()
    expect(wrapper.find('image').exists()).toBe(true)
    expect(store.worldSnapshot).toBeNull()
  })

  it('honors an explicitly empty snapshot instead of showing live account terrain', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot(new Array(16).fill('water'))
    stubCanvas()
    const wrapper = mount(AtlasTerrain, { props: { snapshot: null } })
    await flushPromises()
    expect(wrapper.find('image').exists()).toBe(false)
    expect(store.worldSnapshot).not.toBeNull()
  })

  it('draws an underlay image beneath the masks', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot(new Array(16).fill('wasteland'))
    const ctx = stubCanvas()
    stubMaskTokens()
    class LoadedImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(_value: string) {
        this.onload?.()
      }
    }
    vi.stubGlobal('Image', LoadedImage)

    const wrapper = mount(AtlasTerrain, {
      props: { roads: [0], rivers: [15], underlayUrl: '/plate.png' },
    })
    await flushPromises()

    expect(wrapper.find('.atlas-terrain').attributes('data-underlay')).toBe('loaded')
    expect(ctx.drawImage.mock.calls.some(([source]) => source instanceof LoadedImage)).toBe(true)
  })

  it('keeps procedural terrain when the underlay fails to load', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot(new Array(16).fill('wasteland'))
    stubCanvas()
    class FailedImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(_value: string) {
        this.onerror?.()
      }
    }
    vi.stubGlobal('Image', FailedImage)

    const wrapper = mount(AtlasTerrain, { props: { underlayUrl: '/missing.png' } })
    await flushPromises()

    expect(wrapper.find('.atlas-terrain').attributes('data-underlay')).toBe('failed')
    expect(wrapper.find('image').exists()).toBe(true)
  })

  it('renders vector road edges as strokes instead of tile rects', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot(new Array(16).fill('wasteland'))
    const ctx = stubCanvas()
    stubMaskTokens()

    mount(AtlasTerrain, {
      props: {
        roadEdges: [{ class: 'country', points: [[0.5, 0.5], [1.5, 0.5]] }],
      },
    })
    await flushPromises()

    expect(ctx.fillRect).toHaveBeenCalledTimes(16)
    expect(ctx.stroke).toHaveBeenCalledTimes(2)
  })

  it('renders highways and country roads with separate passes', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot(new Array(16).fill('wasteland'))
    const ctx = stubCanvas()
    stubMaskTokens()

    mount(AtlasTerrain, {
      props: {
        roadEdges: [
          { class: 'country', points: [[0.5, 0.5], [1.5, 0.5]] },
          { class: 'highway', points: [[3.5, 0.5], [3.5, 3.5]] },
        ],
      },
    })
    await flushPromises()

    expect(ctx.stroke).toHaveBeenCalledTimes(5)
    expect(ctx.setLineDash).toHaveBeenCalled()
  })
})
