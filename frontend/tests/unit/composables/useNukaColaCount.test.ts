import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick, ref, type Ref } from 'vue'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import type { QueryClient } from '@tanstack/vue-query'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { authService } from '@/modules/auth/services/authService'
import type { User } from '@/modules/auth/types/user'
import {
  storageService,
  type StorageItemsResponse,
} from '@/modules/storage/services/storageService'
import {
  countNukaColaBottles,
  invalidateNukaColaCount,
  nukaColaCountKey,
  useNukaColaCount,
  type NukaColaCountState,
} from '@/modules/vault/composables/useNukaColaCount'
import { createQueryClient, queryClient as appQueryClient } from '@/core/query/queryClient'
import { mountWithSetup } from '../helpers/mountWithSetup'

vi.mock('@/modules/storage/services/storageService', () => ({
  storageService: { getStorageItems: vi.fn() },
}))

const getStorageItems = vi.mocked(storageService.getStorageItems)

enableAutoUnmount(afterEach)

const userFixture = {
  id: 'user-1',
  username: 'tester',
  email: 'tester@example.com',
  is_active: true,
  is_superuser: false,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} satisfies User

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

function setAuth(accountId: string | null = 'user-1', token: string | null = 'mock-token'): void {
  const auth = useAuthStore()
  auth.token = token
  auth.user = accountId ? { ...userFixture, id: accountId } : null
}

function mountCount(vaultId: Ref<string | null>, client: QueryClient = createQueryClient()) {
  let state: NukaColaCountState | undefined
  const Harness = defineComponent({
    setup() {
      state = useNukaColaCount(vaultId)
      return () => null
    },
  })
  const wrapper = mountWithSetup(Harness, {}, client)
  if (!state) throw new Error('useNukaColaCount did not run during mount')
  return { wrapper, state, client }
}

function expectSignalForwarded(): void {
  const [, options] = getStorageItems.mock.calls[0] ?? []
  expect(options).toEqual(
    expect.objectContaining({
      skipErrorNotification: true,
      signal: expect.any(AbortSignal),
    })
  )
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
  beforeEach(() => {
    vi.clearAllMocks()
    getStorageItems.mockReset()
    localStorage.clear()
    appQueryClient.clear()
  })

  afterEach(() => {
    appQueryClient.clear()
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('stays null until the storage fetch resolves, then exposes the count', async () => {
    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola', 'Nuka-Cola Quantum', 'Stimpak'))
    const { state, wrapper } = mountCount(ref('vault-1'))

    setAuth()

    expect(state.nukaColaCount.value).toBeNull()
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(2)
    expect(getStorageItems).toHaveBeenCalledWith('vault-1', expect.anything())
    expectSignalForwarded()
    wrapper.unmount()
  })

  it('makes no request without an auth token', async () => {
    const { state, wrapper } = mountCount(ref('vault-1'))

    setAuth('user-1', null)
    await flushPromises()

    expect(getStorageItems).not.toHaveBeenCalled()
    expect(state.nukaColaCount.value).toBeNull()
    wrapper.unmount()
  })

  it('makes no request without a resolved account id', async () => {
    const { state, wrapper } = mountCount(ref('vault-1'))

    setAuth(null, 'mock-token')
    await flushPromises()

    expect(getStorageItems).not.toHaveBeenCalled()
    expect(state.nukaColaCount.value).toBeNull()
    wrapper.unmount()
  })

  it('makes no request without a vault id', async () => {
    const { state, wrapper } = mountCount(ref<string | null>(null))

    setAuth()
    await flushPromises()

    expect(getStorageItems).not.toHaveBeenCalled()
    expect(state.nukaColaCount.value).toBeNull()
    wrapper.unmount()
  })

  it('shows a cached count immediately on remount, then revalidates in the background', async () => {
    const client = createQueryClient()
    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola'))

    const vaultId = ref<string | null>('vault-1')
    const first = mountCount(vaultId, client)
    setAuth()
    await flushPromises()
    expect(first.state.nukaColaCount.value).toBe(1)
    first.wrapper.unmount()

    let resolveRefresh!: (value: StorageItemsResponse) => void
    getStorageItems.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRefresh = resolve
        })
    )

    const second = mountCount(vaultId, client)
    setAuth()
    await nextTick()

    expect(second.state.nukaColaCount.value).toBe(1)
    expect(getStorageItems).toHaveBeenCalledTimes(2)

    resolveRefresh(storageItems('Nuka-Cola', 'Nuka-Cola', 'Nuka-Cola'))
    await flushPromises()
    expect(second.state.nukaColaCount.value).toBe(3)
    second.wrapper.unmount()
  })

  it('re-reads after storage changed between visits', async () => {
    const client = createQueryClient()
    getStorageItems.mockResolvedValueOnce(storageItems())
    const vaultId = ref<string | null>('vault-1')

    const first = mountCount(vaultId, client)
    setAuth()
    await flushPromises()
    expect(first.state.nukaColaCount.value).toBe(0)
    first.wrapper.unmount()

    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola'))
    const second = mountCount(vaultId, client)
    setAuth()
    await flushPromises()
    expect(second.state.nukaColaCount.value).toBe(1)
    second.wrapper.unmount()
  })

  it('keeps a real zero distinct from unknown', async () => {
    getStorageItems.mockResolvedValueOnce(storageItems('Stimpak'))
    const { state, wrapper } = mountCount(ref('vault-1'))

    setAuth()
    await flushPromises()

    expect(state.nukaColaCount.value).toBe(0)
    expect(state.nukaColaCount.value).not.toBeNull()
    wrapper.unmount()
  })

  it('shares one in-flight request across concurrent observers', async () => {
    const client = createQueryClient()
    let resolveRequest!: (value: StorageItemsResponse) => void
    getStorageItems.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve
      })
    )

    let firstState: NukaColaCountState | undefined
    let secondState: NukaColaCountState | undefined
    const vaultId = ref<string | null>('vault-1')
    const Harness = defineComponent({
      setup() {
        firstState = useNukaColaCount(vaultId)
        secondState = useNukaColaCount(vaultId)
        return () => null
      },
    })
    const wrapper = mountWithSetup(Harness, {}, client)
    setAuth()
    await nextTick()

    expect(getStorageItems).toHaveBeenCalledTimes(1)
    resolveRequest(storageItems('Nuka-Cola'))
    await flushPromises()

    expect(firstState?.nukaColaCount.value).toBe(1)
    expect(secondState?.nukaColaCount.value).toBe(1)
    wrapper.unmount()
  })

  it('updates a mounted header after a reward invalidation', async () => {
    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola'))
    const { state, wrapper } = mountCount(ref('vault-1'), appQueryClient)
    setAuth()
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola', 'Nuka-Cola', 'Nuka-Cola'))
    await invalidateNukaColaCount('vault-1')
    await flushPromises()

    expect(state.nukaColaCount.value).toBe(3)
    wrapper.unmount()
  })

  it('cancels a pending first load before invalidating, so late old data cannot win', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    let resolveFirst!: (value: StorageItemsResponse) => void
    let firstSignal: AbortSignal | undefined
    getStorageItems
      .mockImplementationOnce((_vaultId, options) => {
        firstSignal = options?.signal
        return new Promise((resolve) => {
          resolveFirst = resolve
        })
      })
      .mockResolvedValueOnce(storageItems('Nuka-Cola'))

    const { state, wrapper } = mountCount(ref('vault-1'), appQueryClient)
    setAuth()
    await vi.waitFor(() => expect(getStorageItems).toHaveBeenCalledTimes(1))

    await invalidateNukaColaCount('vault-1')
    await flushPromises()

    expect(firstSignal?.aborted).toBe(true)
    expect(getStorageItems).toHaveBeenCalledTimes(2)
    expect(state.nukaColaCount.value).toBe(1)

    resolveFirst(storageItems())
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)
    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining('Nuka-Cola count'))
    wrapper.unmount()
  })

  it('cancels a background refetch with a warm cache and ignores its late result', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola'))
    const { state, wrapper } = mountCount(ref('vault-1'), appQueryClient)
    setAuth()
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    let resolveStale!: (value: StorageItemsResponse) => void
    let staleSignal: AbortSignal | undefined
    getStorageItems
      .mockImplementationOnce((_vaultId, options) => {
        staleSignal = options?.signal
        return new Promise((resolve) => {
          resolveStale = resolve
        })
      })
      .mockResolvedValueOnce(storageItems('Nuka-Cola', 'Nuka-Cola'))

    void appQueryClient.invalidateQueries({
      queryKey: nukaColaCountKey('user-1', 'vault-1'),
      exact: true,
    })
    await vi.waitFor(() => expect(getStorageItems).toHaveBeenCalledTimes(2))

    await invalidateNukaColaCount('vault-1')
    await flushPromises()

    expect(staleSignal?.aborted).toBe(true)
    expect(getStorageItems).toHaveBeenCalledTimes(3)
    expect(state.nukaColaCount.value).toBe(2)

    resolveStale(storageItems())
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(2)
    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining('Nuka-Cola count'))
    wrapper.unmount()
  })

  it('logs once and leaves the count unknown when the first load fails', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    getStorageItems.mockRejectedValueOnce(new Error('offline'))

    const { state, wrapper } = mountCount(ref('vault-1'))
    setAuth()
    await flushPromises()

    expect(getStorageItems).toHaveBeenCalledTimes(1)
    expect(state.nukaColaCount.value).toBeNull()
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('Nuka-Cola count stays unloaded'))
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('vault-1'))
    wrapper.unmount()
  })

  it('keeps the last good value when a refetch fails', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola'))
    const { state, wrapper } = mountCount(ref('vault-1'), appQueryClient)
    setAuth()
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    getStorageItems.mockRejectedValueOnce(new Error('offline'))
    await invalidateNukaColaCount('vault-1').catch(() => undefined)
    await flushPromises()

    expect(state.nukaColaCount.value).toBe(1)
    expect(appQueryClient.getQueryState(nukaColaCountKey('user-1', 'vault-1'))?.status).toBe(
      'error'
    )
    expect(warn).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('isolates counts by vault', async () => {
    const client = createQueryClient()
    getStorageItems.mockImplementation((vaultId) =>
      Promise.resolve(
        vaultId === 'vault-1' ? storageItems('Nuka-Cola') : storageItems('Nuka-Cola', 'Nuka-Cola')
      )
    )

    const first = mountCount(ref('vault-1'), client)
    setAuth()
    await flushPromises()
    expect(first.state.nukaColaCount.value).toBe(1)

    const second = mountCount(ref('vault-2'), client)
    setAuth()
    await flushPromises()
    expect(second.state.nukaColaCount.value).toBe(2)

    const countKeys = client
      .getQueryCache()
      .getAll()
      .filter(
        (query) =>
          query.queryKey[1] === 'nuka-cola-count' &&
          query.queryKey[2] === 'user-1' &&
          query.queryKey[3] !== null
      )
    expect(countKeys).toHaveLength(2)
    first.wrapper.unmount()
    second.wrapper.unmount()
  })

  it('hides the previous account immediately when the account changes', async () => {
    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola'))
    const { state, wrapper } = mountCount(ref('vault-1'), appQueryClient)
    setAuth('user-a')
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola', 'Nuka-Cola'))
    setAuth('user-b')
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(2)
    wrapper.unmount()
  })

  it('ignores a pending previous-account response after switching accounts', async () => {
    let resolveFirst!: (value: StorageItemsResponse) => void
    let resolveSecond!: (value: StorageItemsResponse) => void
    getStorageItems
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve
          })
      )

    const { state, wrapper } = mountCount(ref('vault-1'), appQueryClient)
    setAuth('user-a')
    await vi.waitFor(() => expect(getStorageItems).toHaveBeenCalledTimes(1))

    setAuth('user-b')
    await vi.waitFor(() => expect(getStorageItems).toHaveBeenCalledTimes(2))

    resolveSecond(storageItems('Nuka-Cola'))
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    resolveFirst(storageItems('Nuka-Cola', 'Nuka-Cola'))
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)
    wrapper.unmount()
  })

  it('drops a pending previous-account response on logout', async () => {
    let resolvePending!: (value: StorageItemsResponse) => void
    getStorageItems.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolvePending = resolve
        })
    )

    const { state, wrapper } = mountCount(ref('vault-1'), appQueryClient)
    setAuth('user-a')
    await vi.waitFor(() => expect(getStorageItems).toHaveBeenCalledTimes(1))

    vi.spyOn(authService, 'logout').mockResolvedValue(undefined as never)
    await useAuthStore().logout()
    await flushPromises()

    expect(state.nukaColaCount.value).toBeNull()
    expect(appQueryClient.getQueryData(nukaColaCountKey('user-a', 'vault-1'))).toBeUndefined()

    resolvePending(storageItems('Nuka-Cola'))
    await flushPromises()

    expect(state.nukaColaCount.value).toBeNull()
    expect(appQueryClient.getQueryData(nukaColaCountKey('user-a', 'vault-1'))).toBeUndefined()
    wrapper.unmount()
  })

  it('clears account data on logout', async () => {
    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola'))
    const { state, wrapper } = mountCount(ref('vault-1'), appQueryClient)
    setAuth()
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    vi.spyOn(authService, 'logout').mockResolvedValue(undefined as never)
    await useAuthStore().logout()
    await flushPromises()

    expect(appQueryClient.getQueryData(nukaColaCountKey('user-1', 'vault-1'))).toBeUndefined()
    expect(
      appQueryClient
        .getQueryCache()
        .getAll()
        .every((query) => query.state.data === undefined)
    ).toBe(true)
    expect(state.nukaColaCount.value).toBeNull()
    wrapper.unmount()
  })

  it('does not refetch when the same account rotates its access token', async () => {
    getStorageItems.mockResolvedValue(storageItems('Nuka-Cola'))
    const { state, wrapper } = mountCount(ref('vault-1'), createQueryClient())
    setAuth('user-1', 'token-1')
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    setAuth('user-1', 'token-2')
    await flushPromises()

    expect(getStorageItems).toHaveBeenCalledTimes(1)
    expect(state.nukaColaCount.value).toBe(1)
    wrapper.unmount()
  })

  it('applies the auth gate even with a warm cache', async () => {
    getStorageItems.mockResolvedValueOnce(storageItems('Nuka-Cola'))
    const { state, wrapper } = mountCount(ref('vault-1'), createQueryClient())
    setAuth()
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    setAuth('user-1', null)
    await nextTick()
    expect(state.nukaColaCount.value).toBeNull()
    wrapper.unmount()
  })

  it('does not refetch on window focus or reconnect', async () => {
    getStorageItems.mockResolvedValue(storageItems('Nuka-Cola'))
    const { state, wrapper } = mountCount(ref('vault-1'), createQueryClient())
    setAuth()
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)

    window.dispatchEvent(new Event('focus'))
    window.dispatchEvent(new Event('online'))
    await flushPromises()

    expect(getStorageItems).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('ignores a late count from a vault the header has left', async () => {
    const resolvers: Array<(value: StorageItemsResponse) => void> = []
    getStorageItems.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvers.push(resolve)
        })
    )

    const vaultId = ref<string | null>('vault-1')
    const { state, wrapper } = mountCount(vaultId, createQueryClient())
    setAuth()
    await vi.waitFor(() => expect(resolvers).toHaveLength(1))

    vaultId.value = 'vault-2'
    await vi.waitFor(() => expect(resolvers).toHaveLength(2))

    resolvers[0](storageItems('Nuka-Cola', 'Nuka-Cola'))
    await flushPromises()
    expect(state.nukaColaCount.value).toBeNull()

    resolvers[1](storageItems('Nuka-Cola'))
    await flushPromises()
    expect(state.nukaColaCount.value).toBe(1)
    wrapper.unmount()
  })
})
