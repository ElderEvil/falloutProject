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

  function stubCanvas() {
    const calls = { fillRect: 0, drawImage: 0, getImageData: 0, putImageData: 0 }
    const ctx = {
      fillStyle: '',
      imageSmoothingEnabled: false,
      imageSmoothingQuality: 'low',
      fillRect: vi.fn(() => {
        calls.fillRect += 1
      }),
      drawImage: vi.fn(() => {
        calls.drawImage += 1
      }),
      getImageData: vi.fn((_x: number, _y: number, w: number, h: number) => {
        calls.getImageData += 1
        return { data: new Uint8ClampedArray(w * h * 4) }
      }),
      putImageData: vi.fn(() => {
        calls.putImageData += 1
      }),
    }
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx as any)
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,x')
    return calls
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

  it('paints every snapshot cell, blends, and shows the terrain image', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot([
      'water', 'forest', 'hills', 'ruins',
      ...new Array(12).fill('wasteland'),
    ])
    const calls = stubCanvas()

    const wrapper = mount(AtlasTerrain)
    await flushPromises()

    expect(calls.fillRect).toBe(16)
    // Bilinear upscale (blend) then dither pass.
    expect(calls.drawImage).toBe(1)
    expect(calls.getImageData).toBe(1)
    expect(calls.putImageData).toBe(1)
    expect(wrapper.find('image').exists()).toBe(true)
  })

  it('renders no terrain and no roads without a snapshot', async () => {
    const store = useMapStore()
    store.worldSnapshot = null
    stubCanvas()

    const wrapper = mount(AtlasTerrain)
    await flushPromises()

    expect(wrapper.find('image').exists()).toBe(false)
    expect(wrapper.findAll('path')).toHaveLength(0)
  })
})
