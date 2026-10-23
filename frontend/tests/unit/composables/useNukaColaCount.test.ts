import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises } from '@vue/test-utils'
import { effectScope, nextTick, ref, type EffectScope, type Ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import {
  countNukaColaBottles,
  refreshNukaColaCount,
  useNukaColaCount,
  type NukaColaCountState,
} from '@/modules/vault/composables/useNukaColaCount'
import { useAuthStore } from '@/modules/auth/stores/auth'
import {
  storageService,
  type StorageItemsResponse,
} from '@/modules/storage/services/storageService'

vi.mock('@/modules/storage/services/storageService', () => ({
  storageService: { getStorageItems: vi.fn() },
}))

function storageItems(...names: string[]): StorageItemsResponse {
  return {
    weapons: [],
    outfits: [],
    junk: [],
    pets: [],
    items: names.map((name, index) => ({
      id: `item-${index}`,
      name,
      item_type: 'consumable',
      rarity: 'common',
      storage_id: null,
    })),
  }
}

function newCache(): Map<string, Ref<number | null>> {
  return new Map<string, Ref<number | null>>()
}

describe('countNukaColaBottles', () => {
  it('counts every item whose name references Nuka-Cola', () => {
    expect(countNukaColaBottles([{ name: 'Nuka-Cola Quantum' }, { name: 'nuka-cola' }])).toBe(2)
  })

  it('ignores items unrelated to Nuka-Cola', () => {
    expect(countNukaColaBottles([{ name: 'Stimpak' }, { name: 'RadAway' }])).toBe(0)
  })

  it('returns zero for an empty list', () => {
    expect(countNukaColaBottles([])).toBe(0)
  })
})

describe('useNukaColaCount', () => {
  let scope: EffectScope

  beforeEach(() => {
    scope = effectScope()
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'mock-token'
  })

  // Watchers created outside a component are not auto-disposed; stopping the
  // scope keeps one test's watcher from reacting to the next test's token ref.
  afterEach(() => {
    scope.stop()
  })

  function useCount(
    vaultId: Ref<string | null>,
    cache?: Map<string, Ref<number | null>>
  ): NukaColaCountState {
    const state = scope.run(() =>
      useNukaColaCount(vaultId, cache as Map<string, Ref<number | null>> | undefined)
    )
    if (!state) throw new Error('composable did not run inside the effect scope')
    return state
  }

  it('stays null until the storage fetch resolves, then exposes the count', async () => {
    vi.mocked(storageService.getStorageItems).mockResolvedValueOnce(
      storageItems('Nuka-Cola', 'Nuka-Cola Quantum', 'Stimpak')
    )

    const { nukaColaCount } = useCount(ref('vault-1'))

    expect(nukaColaCount.value).toBeNull()
    await flushPromises()
    expect(nukaColaCount.value).toBe(2)
    expect(storageService.getStorageItems).toHaveBeenCalledWith('vault-1')
  })

  it('makes no request when the auth token is empty', async () => {
    useAuthStore().token = null
    const { nukaColaCount } = useCount(ref('vault-1'))

    await flushPromises()

    expect(storageService.getStorageItems).not.toHaveBeenCalled()
    expect(nukaColaCount.value).toBeNull()
  })

  it('makes no request off a vault route', async () => {
    useCount(ref<string | null>(null))

    await flushPromises()

    expect(storageService.getStorageItems).not.toHaveBeenCalled()
  })

  it('serves a cached count on remount and revalidates in the background', async () => {
    const cache = newCache()
    vi.mocked(storageService.getStorageItems).mockResolvedValue(storageItems('Nuka-Cola'))

    const first = useCount(ref('vault-1'), cache)
    await flushPromises()
    expect(first.nukaColaCount.value).toBe(1)

    const second = useCount(ref('vault-1'), cache)
    expect(second.nukaColaCount.value).toBe(1)
    await flushPromises()
    expect(storageService.getStorageItems).toHaveBeenCalledTimes(2)
    expect(second.nukaColaCount.value).toBe(1)
  })

  it('re-reads after storage changed between visits (stale cache never sticks)', async () => {
    const cache = newCache()
    vi.mocked(storageService.getStorageItems).mockResolvedValueOnce(storageItems())

    useCount(ref('vault-1'), cache)
    await flushPromises()

    const returned = useCount(ref('vault-1'), cache)
    expect(returned.nukaColaCount.value).toBe(0)
    vi.mocked(storageService.getStorageItems).mockResolvedValueOnce(storageItems('Nuka-Cola'))
    await flushPromises()
    expect(returned.nukaColaCount.value).toBe(1)
  })

  it('refreshNukaColaCount updates shared-default mounted headers after a claim', async () => {
    vi.mocked(storageService.getStorageItems).mockResolvedValue(storageItems('Nuka-Cola'))

    const { nukaColaCount } = useCount(ref('vault-1'))
    await flushPromises()
    expect(nukaColaCount.value).toBe(1)

    vi.mocked(storageService.getStorageItems).mockResolvedValue(
      storageItems('Nuka-Cola', 'Nuka-Cola', 'Nuka-Cola')
    )
    await refreshNukaColaCount('vault-1')

    expect(nukaColaCount.value).toBe(3)
  })

  it('shares one in-flight request across concurrent mounts', async () => {
    let resolveRequest!: (value: StorageItemsResponse) => void
    vi.mocked(storageService.getStorageItems).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve
      })
    )

    const cache = newCache()
    const first = useCount(ref('vault-1'), cache)
    const second = useCount(ref('vault-1'), cache)

    expect(storageService.getStorageItems).toHaveBeenCalledTimes(1)
    resolveRequest(storageItems('Nuka-Cola'))
    await flushPromises()

    expect(first.nukaColaCount.value).toBe(1)
    expect(second.nukaColaCount.value).toBe(1)
  })

  it.each([false, true])('refreshes after an older request settles (failed=%s)', async (failed) => {
    const cache = newCache()
    let resolveOld!: (value: StorageItemsResponse) => void
    let rejectOld!: (reason: Error) => void
    vi.mocked(storageService.getStorageItems)
      .mockReturnValueOnce(
        new Promise((resolve, reject) => {
          resolveOld = resolve
          rejectOld = reject
        })
      )
      .mockResolvedValue(storageItems('Nuka-Cola'))
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const state = useCount(ref('claim-race'), cache)
    const refreshed = refreshNukaColaCount('claim-race', cache)
    try {
      if (failed) rejectOld(new Error('old request failed'))
      else resolveOld(storageItems())
      await refreshed
      await flushPromises()
      expect(state.nukaColaCount.value).toBe(1)
      expect(storageService.getStorageItems).toHaveBeenCalledTimes(2)
    } finally {
      warn.mockRestore()
    }
  })

  it('keeps the count unloaded when the storage fetch fails and logs context', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.mocked(storageService.getStorageItems).mockRejectedValueOnce(new Error('offline'))

    const { nukaColaCount } = useCount(ref('vault-1'), newCache())

    await flushPromises()
    expect(nukaColaCount.value).toBeNull()
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('Nuka-Cola count stays unloaded'))
    warnSpy.mockRestore()
  })

  it('ignores a late count from a vault the header has left', async () => {
    const resolvers: Array<(value: StorageItemsResponse) => void> = []
    vi.mocked(storageService.getStorageItems).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvers.push(resolve)
        })
    )

    const vaultId = ref<string | null>('vault-1')
    const { nukaColaCount } = useCount(vaultId)

    vaultId.value = 'vault-2'
    await nextTick()

    resolvers[0](storageItems('Nuka-Cola', 'Nuka-Cola'))
    await flushPromises()
    expect(nukaColaCount.value).toBeNull()

    resolvers[1](storageItems('Nuka-Cola'))
    await flushPromises()
    expect(nukaColaCount.value).toBe(1)
  })
})
