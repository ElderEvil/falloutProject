import { describe, expect, it, beforeEach, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MapLabView from '@/modules/map/views/MapLabView.vue'
import RegionOverlay from '@/modules/map/components/RegionOverlay.vue'
import { Switch } from '@/core/components/ui/switch'
import { getWorldPreview } from '@/modules/map/services/mapLabService'
import type { WorldSnapshotRead } from '@/modules/map/models/map'

vi.mock('@/modules/map/services/mapLabService', () => ({
  getWorldPreview: vi.fn(),
}))

vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
  getErrorMessage: () => 'offline',
}))

const WORLD = {
  world_id: 'wasteland-atlas',
  generator_version: 3,
  recipe_fingerprint: 'abcdef0123456789',
  snapshot_checksum: '0123456789abcdef',
  width: 4,
  height: 4,
  terrain: ['wasteland', 'forest', 'hills', 'ruins', 'wasteland', 'wasteland', 'wasteland', 'wasteland', 'wasteland', 'wasteland', 'wasteland', 'wasteland', 'wasteland', 'wasteland', 'wasteland', 'wasteland'],
  slots: [{ slot_index: 0, coord_x: 50, coord_y: 50 }],
  roads: [1],
  rivers: [],
  road_edges: [
    { class: 'highway', points: [[0.5, 0.5], [1.5, 1.5]] },
    { class: 'country', points: [[2.5, 2.5], [3.5, 3.5]] },
  ],
  regions: [
    { id: 'green_belt', name: 'Green Belt', danger_tier: 1, center_x: 20, center_y: 20, biome: {} },
  ],
  region_map: new Array(16).fill(0),
  places: [],
  validation: {
    regions: { green_belt: { tiles: 16, terrain: { wasteland: 16 }, in_main_component: 16 } },
    isolated_regions: [],
    slot_tiles: 1,
    reachable_slot_tiles: 1,
  },
} as WorldSnapshotRead

function mountLab() {
  return mount(MapLabView, {
    global: {
      stubs: { RouterLink: { template: '<a><slot /></a>' }, AtlasTerrain: true },
    },
  })
}

describe('MapLabView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders the generated world counts, regions, and validation', async () => {
    vi.mocked(getWorldPreview).mockResolvedValue(WORLD)
    const wrapper = mountLab()
    await flushPromises()

    expect(getWorldPreview).toHaveBeenCalledWith('wasteland-atlas-v1')
    expect(wrapper.text()).toContain('Green Belt')
    expect(wrapper.text()).toContain('16 tiles')
    expect(wrapper.text()).toContain('1 / 1')
    expect(wrapper.findComponent(RegionOverlay).props('visible')).toBe(true)
  })

  it('toggles the region overlay without dropping the generated world', async () => {
    vi.mocked(getWorldPreview).mockResolvedValue(WORLD)
    const wrapper = mountLab()
    await flushPromises()

    await wrapper.findAllComponents(Switch)[1].vm.$emit('update:checked', false)
    await flushPromises()

    expect(wrapper.findComponent(RegionOverlay).exists()).toBe(false)
    expect(wrapper.text()).toContain('Green Belt')
  })

  it('shows an error when generation fails', async () => {
    vi.mocked(getWorldPreview).mockRejectedValue(new Error('offline'))
    const wrapper = mountLab()
    await flushPromises()

    expect(wrapper.get('[role="status"]').text()).toContain('Generation failed: offline')
  })
})
