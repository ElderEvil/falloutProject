import { describe, expect, it, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import AtlasTerrain from '@/modules/map/components/AtlasTerrain.vue'
import { useMapStore } from '@/modules/map/stores/map'

describe('AtlasTerrain', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  // Minimal canvas stub: blending/dither are cosmetic, so tests assert only that
  // the terrain image renders and is stable — not the rasterisation strategy.
  function stubCanvas() {
    const ctx = {
      fillStyle: '',
      imageSmoothingEnabled: false,
      imageSmoothingQuality: 'low',
      fillRect: vi.fn(),
      drawImage: vi.fn(),
      getImageData: vi.fn((_x: number, _y: number, w: number, h: number) => ({
        data: new Uint8ClampedArray(w * h * 4),
      })),
      putImageData: vi.fn(),
    }
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx as any)
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,x')
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
      'water', 'forest', 'hills', 'ruins',
      ...new Array(12).fill('wasteland'),
    ])
    stubCanvas()

    const wrapper = mount(AtlasTerrain)
    await flushPromises()

    expect(wrapper.find('image').exists()).toBe(true)
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
})
