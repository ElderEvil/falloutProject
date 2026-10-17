import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { storageService } from '@/modules/storage/services/storageService'

export interface NukaColaCountState {
  nukaColaCount: Ref<number | null>
  nukaColaTooltip: ComputedRef<string>
}

// Nuka-Cola is not a vault field: rewards land as generic storage items, so the
// count is a case-insensitive name match over the vault's stored item list.
const NUKA_COLA_NAME_PATTERN = /nuka/i

// Counts survive NavBar remounts and route changes within a session so returning
// to a vault does not refetch its storage. Injectable for test isolation.
const sharedCounts = new Map<string, number>()
// Concurrent mounts of the same vault share one in-flight request.
const inFlightCounts = new Map<string, Promise<number>>()

/** Count the vault's stored items whose name references Nuka-Cola. */
export function countNukaColaBottles(items: ReadonlyArray<{ name: string }>): number {
  return items.reduce(
    (total, item) => (NUKA_COLA_NAME_PATTERN.test(item.name) ? total + 1 : total),
    0
  )
}

async function loadNukaColaCount(vaultId: string, counts: Map<string, number>): Promise<number> {
  const cached = counts.get(vaultId)
  if (cached !== undefined) return cached

  const inFlight = inFlightCounts.get(vaultId)
  if (inFlight) return inFlight

  const request = storageService
    .getStorageItems(vaultId)
    .then((storage) => countNukaColaBottles(storage.items))
  inFlightCounts.set(vaultId, request)
  try {
    const count = await request
    counts.set(vaultId, count)
    return count
  } finally {
    inFlightCounts.delete(vaultId)
  }
}

/**
 * Route-aware Nuka-Cola bottle count for the shell header.
 *
 * `nukaColaCount` is `null` until the storage fetch resolves — never a false `0`,
 * which would read as "none stored". A failed fetch is non-fatal: the count stays
 * `null` and the header keeps its dash. Fetches only run with a vault id AND a
 * token, are cached per vault id, and concurrent mounts of one vault share a
 * single request.
 */
export function useNukaColaCount(
  vaultId: Ref<string | null>,
  counts: Map<string, number> = sharedCounts
): NukaColaCountState {
  const authStore = useAuthStore()
  const nukaColaCount = ref<number | null>(null)

  watch(
    [vaultId, () => authStore.token],
    ([id, token]) => {
      if (!id || !token) {
        nukaColaCount.value = null
        return
      }

      const cached = counts.get(id)
      if (cached !== undefined) {
        nukaColaCount.value = cached
        return
      }

      // Stay null until the real count lands; a placeholder 0 would read as
      // "none stored" rather than "not loaded".
      nukaColaCount.value = null
      void loadNukaColaCount(id, counts)
        .then((count) => {
          if (vaultId.value === id && authStore.token === token) nukaColaCount.value = count
        })
        .catch(() => {
          // Non-fatal: a storage failure must not break the vault header. The
          // count simply stays "not loaded" and the metric keeps its dash.
        })
    },
    { immediate: true }
  )

  const nukaColaTooltip = computed(() =>
    nukaColaCount.value === null
      ? 'Nuka-Cola bottles stored in your vault'
      : `Nuka-Cola bottles stored in your vault: ${nukaColaCount.value}`
  )

  return { nukaColaCount, nukaColaTooltip }
}
