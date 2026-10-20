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
    expect(await store.refresh('vault-1')).toBe('loaded')
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
    expect(await refresh).toBe('stale')
    expect(store.maintenance).toBeNull()
    expect(store.items.weapons).toEqual([])
  })
})

it('distinguishes an overlapping refresh from an active request failure', async () => {
  const pending: Array<(response: { data: unknown }) => void> = []
  vi.mocked(axios.get).mockImplementation(() => new Promise((resolve) => pending.push(resolve)))
  const store = useStorageStore()
  const first = store.refresh('vault-1')
  const second = store.refresh('vault-1')
  pending.slice(3).forEach((resolve) => resolve({ data: summary }))
  expect(await second).toBe('loaded')
  pending.slice(0, 3).forEach((resolve) => resolve({ data: {} }))
  expect(await first).toBe('stale')
  expect(store.maintenance).toEqual(summary)
  expect(store.isLoading).toBe(false)
  vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network down'))
  expect(await store.refresh('vault-1')).toBe('error')
  expect(store.isLoading).toBe(false)
})

it('keeps tick refreshes while a consumer remains and stops after the last release', async () => {
  vi.mocked(axios.get).mockResolvedValue({ data: summary })
  const store = useStorageStore()
  const releaseView = store.retain()
  const releasePanel = store.retain()
  await store.refresh('vault-1')
  vi.mocked(axios.get).mockClear()
  releaseView()
  store.refreshIfActive('vault-1')
  expect(axios.get).toHaveBeenCalledTimes(3)
  releasePanel()
  vi.mocked(axios.get).mockClear()
  store.refreshIfActive('vault-1')
  expect(axios.get).not.toHaveBeenCalled()
  expect(store.vaultId).toBeNull()
})

it('ignores a stale failure after a newer refresh has loaded', async () => {
  let fail!: (reason: Error) => void
  vi.mocked(axios.get).mockImplementationOnce(
    () =>
      new Promise((resolve, reject) => {
        fail = reject
      })
  )
  vi.mocked(axios.get).mockResolvedValue({ data: summary })
  const store = useStorageStore()
  const first = store.refresh('vault-1')
  expect(await store.refresh('vault-1')).toBe('loaded')
  fail(new Error('Superseded network error'))
  expect(await first).toBe('stale')
  expect(store.maintenance).toEqual(summary)
})
