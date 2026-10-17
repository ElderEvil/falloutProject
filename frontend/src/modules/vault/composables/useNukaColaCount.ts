import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { storageService } from '@/modules/storage/services/storageService'

export interface NukaColaCountState {
  nukaColaCount: Ref<number | null>
  nukaColaTooltip: ComputedRef<string>
}

// Nuka-Cola is not a vault field: rewards land as generic storage items, so the
// count is a case-insensitive name match over the vault's stored item list.
const NUKA_COLA_NAME_PATTERN = /nuka/i

// One reactive owner per vault id: every mounted header shares the same Ref, so
// a refresh updates them all in place. Injectable for test isolation.
const sharedCounts = new Map<string, Ref<number | null>>()
// Concurrent activations of the same vault share one in-flight request.
const inFlightCounts = new Map<string, Promise<number>>()

/** Count the vault's stored items whose name references Nuka-Cola. */
export function countNukaColaBottles(items: ReadonlyArray<{ name: string }>): number {
  return items.reduce(
    (total, item) => (NUKA_COLA_NAME_PATTERN.test(item.name) ? total + 1 : total),
    0
  )
}

function cacheFor(vaultId: string, counts: Map<string, Ref<number | null>>): Ref<number | null> {
  let entry = counts.get(vaultId)
  if (!entry) {
    entry = ref<number | null>(null)
    counts.set(vaultId, entry)
  }
  return entry
}

async function fetchNukaColaCount(vaultId: string, entry: Ref<number | null>): Promise<number> {
  const inFlight = inFlightCounts.get(vaultId)
  if (inFlight) return inFlight

  const request = storageService
    .getStorageItems(vaultId)
    .then((storage) => countNukaColaBottles(storage.items))
  inFlightCounts.set(vaultId, request)
  try {
    const count = await request
    entry.value = count
    return count
  } finally {
    inFlightCounts.delete(vaultId)
  }
}

function logUnload(vaultId: string, error: unknown): void {
  console.warn(`Nuka-Cola count stays unloaded: vault ${vaultId}: ${getErrorMessage(error)}`)
}

/**
 * Route-aware Nuka-Cola bottle count for the shell header.
 *
 * `nukaColaCount` is `null` until a storage fetch resolves — never a false `0`,
 * which would read as "none stored". Every activation revalidates: a mount with
 * a cached value renders it immediately and refetches in the background, so
 * rewards granted between visits cannot leave the header stale. A failed fetch
 * is logged and non-fatal: the count keeps its current value (or stays `null`,
 * so the header shows its dash) instead of breaking the vault shell.
 */
export function useNukaColaCount(
  vaultId: Ref<string | null>,
  counts: Map<string, Ref<number | null>> = sharedCounts
): NukaColaCountState {
  const authStore = useAuthStore()

  const nukaColaCount = computed<number | null>(() => {
    const id = vaultId.value
    return id && authStore.token ? (counts.get(id)?.value ?? null) : null
  })

  watch(
    [vaultId, () => authStore.token],
    ([id, token]) => {
      if (!id || !token) return
      const entry = cacheFor(id, counts)
      void fetchNukaColaCount(id, entry).catch((error: unknown) => logUnload(id, error))
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

/**
 * Re-read the bottle count now, after storage mutations (reward claims, sales).
 * Headers sharing the vault's cached Ref update in place; on fetch failure the
 * cached value is kept (never dropped to `null` by a refresh attempt).
 */
export async function refreshNukaColaCount(
  vaultId: string,
  counts: Map<string, Ref<number | null>> = sharedCounts
): Promise<void> {
  // A request started before the mutation can contain the old inventory. Its
  // owner handles errors; refresh still needs a new read after it settles.
  await inFlightCounts.get(vaultId)?.catch(() => undefined)
  const entry = cacheFor(vaultId, counts)
  return fetchNukaColaCount(vaultId, entry)
    .then(() => undefined)
    .catch((error: unknown) => logUnload(vaultId, error))
}
