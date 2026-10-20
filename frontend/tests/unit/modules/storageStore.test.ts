import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useStorageStore } from '@/modules/storage/stores/storage'

vi.mock('@/core/plugins/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

const inventory = { weapons: [], outfits: [], junk: [], items: [], pets: [] }
const summary = {
  enabled: true,
  worker_count: 2,
  total_endurance: 40,
  protection_pct: 100,
  mode: 'improving',
  hourly_chance: 0.02,
  trial_interval_seconds: 3600,
}

describe('storage state', () => {
  it('loads inventory and the actual hourly maintenance odds together', async () => {
    vi.mocked(axios.get).mockImplementation(async (url) => ({
      data: String(url).endsWith('/maintenance')
        ? summary
        : String(url).endsWith('/items')
          ? inventory
          : { used_space: 0 },
    }))
    const store = useStorageStore()
    expect(await store.refresh('vault-1')).toBe(true)
    expect(store.maintenanceLabel).toBe('Improving · 2.0% / hour')
    expect(store.maintenance?.total_endurance).toBe(40)
    store.reset()
    expect(store.maintenance).toBeNull()
    expect(store.vaultId).toBeNull()
  })

  it('does not restore account-owned data after logout during a request', async () => {
    const pending: Array<(response: { data: unknown }) => void> = []
    vi.mocked(axios.get).mockImplementation(() => new Promise((resolve) => pending.push(resolve)))
    const store = useStorageStore()
    const refresh = store.refresh('vault-1')
    store.reset()
    pending.forEach((finish) => finish({ data: summary }))
    expect(await refresh).toBe(false)
    expect(store.maintenance).toBeNull()
    expect(store.items.weapons).toEqual([])
  })
})
