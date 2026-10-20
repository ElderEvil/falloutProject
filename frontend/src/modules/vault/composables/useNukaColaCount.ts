import { computed, type ComputedRef, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { storageService } from '@/modules/storage/services/storageService'
import { queryClient } from '@/core/query/queryClient'

export interface NukaColaCountState {
  nukaColaCount: ComputedRef<number | null>
  nukaColaTooltip: ComputedRef<string>
}

/**
 * Cache key for one account's count of Nuka-Cola bottles in one vault.
 *
 * Account and vault IDs scope the entry; tokens are deliberately excluded so
 * an access-token refresh does not create a second cache entry.
 */
export function nukaColaCountKey(
  accountId: string | null,
  vaultId: string | null
): readonly ['storage', 'nuka-cola-count', string | null, string | null] {
  return ['storage', 'nuka-cola-count', accountId, vaultId] as const
}

// Nuka-Cola is not a vault field: rewards land as generic storage items, so the
// count is a case-insensitive name match over the vault's stored item list.
const NUKA_COLA_NAME_PATTERN = /nuka/i

/** Count the vault's stored items whose name references Nuka-Cola. */
export function countNukaColaBottles(items: ReadonlyArray<{ name: string }>): number {
  return items.reduce(
    (total, item) => (NUKA_COLA_NAME_PATTERN.test(item.name) ? total + 1 : total),
    0
  )
}

/**
 * Route-aware Nuka-Cola bottle count for the shell header.
 *
 * `nukaColaCount` is `null` until a storage fetch resolves — never a false `0`,
 * which would read as "none stored". The auth/account/vault gate is applied both
 * to `enabled` and to the returned computed: a disabled query can still serve a
 * warm cache, and a mounted observer can briefly retain the previous account's
 * result while auth changes.
 *
 * A background refetch failure keeps the last good value; only a failed first
 * load leaves the count unknown. Failures are logged by the QueryClient's
 * `QueryCache.onError`, not surfaced as a header error state.
 */
export function useNukaColaCount(vaultId: Ref<string | null>): NukaColaCountState {
  const authStore = useAuthStore()

  const accountId = computed(() => authStore.user?.id ?? null)
  const isEnabled = computed(() => Boolean(authStore.token && accountId.value && vaultId.value))
  const queryKey = computed(() => nukaColaCountKey(accountId.value, vaultId.value))

  const { data } = useQuery({
    queryKey,
    queryFn: async ({ signal, queryKey: key }) => {
      const id = key[3]
      if (typeof id !== 'string') {
        throw new Error('Nuka-Cola count queried without a vault id')
      }
      const storage = await storageService.getStorageItems(id, {
        signal,
        skipErrorNotification: true,
      })
      return countNukaColaBottles(storage.items)
    },
    enabled: isEnabled,
    retry: false,
    staleTime: 0,
    refetchOnMount: true,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    networkMode: 'always',
    meta: computed(() => ({
      errorContext: `Nuka-Cola count stays unloaded (vault ${vaultId.value ?? 'unknown'})`,
    })),
  })

  const nukaColaCount = computed<number | null>(() =>
    isEnabled.value ? (data.value ?? null) : null
  )

  const nukaColaTooltip = computed(() =>
    nukaColaCount.value === null
      ? 'Nuka-Cola bottles stored in your vault'
      : `Nuka-Cola bottles stored in your vault: ${nukaColaCount.value}`
  )

  return { nukaColaCount, nukaColaTooltip }
}

/**
 * Re-read the bottle count after a storage mutation.
 *
 * Explicit cancellation comes first: during a cold first load, invalidating
 * alone reuses the in-flight promise (its response may predate the mutation).
 * Cancelling aborts that request, then invalidation starts a fresh one for any
 * active observer. The account is rechecked after the await so a logout or
 * account replacement during cancellation cannot start a stale fetch.
 */
export async function invalidateNukaColaCount(vaultId: string): Promise<void> {
  const authStore = useAuthStore()
  const accountId = authStore.user?.id
  if (!authStore.token || !accountId || !vaultId) return

  const filters = { queryKey: nukaColaCountKey(accountId, vaultId), exact: true }
  await queryClient.cancelQueries(filters)
  if (!authStore.token || authStore.user?.id !== accountId) return
  await queryClient.invalidateQueries({ ...filters, refetchType: 'active' })
}
