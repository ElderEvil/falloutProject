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
    const calls = { fillRect: 0 }
    const ctx = {
      fillStyle: '',
      fillRect: vi.fn(() => {
        calls.fillRect += 1
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

  it('paints every snapshot cell and shows the terrain image', async () => {
    const store = useMapStore()
    store.worldSnapshot = snapshot([
      'water', 'forest', 'hills', 'ruins',
      ...new Array(12).fill('wasteland'),
    ])
    const calls = stubCanvas()

    const wrapper = mount(AtlasTerrain)
    await flushPromises()

    expect(calls.fillRect).toBe(16)
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
