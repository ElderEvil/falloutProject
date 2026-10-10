import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { getHappinessLevel, type HappinessLevel } from '@/modules/dwellers/models/dweller'
import { useVaultStore, type VaultWithNumbers } from '../stores/vault'

export type ResourceRates = Record<'power' | 'food' | 'water', number>

export interface VaultHeaderContext {
  isVaultRoute: ComputedRef<boolean>
  vaultId: ComputedRef<string | null>
  vault: ComputedRef<VaultWithNumbers | null>
  isReady: ComputedRef<boolean>
  loadFailed: Ref<boolean>
  dwellersCount: ComputedRef<number>
  populationMax: ComputedRef<number>
  populationUtilization: ComputedRef<number>
  populationColor: ComputedRef<string>
  happiness: ComputedRef<number>
  happinessColor: ComputedRef<string>
  energy: ComputedRef<{ current: number; max: number }>
  food: ComputedRef<{ current: number; max: number }>
  water: ComputedRef<{ current: number; max: number }>
  resourceRates: ComputedRef<ResourceRates | undefined>
  bottleCaps: ComputedRef<number>
  dwellersTooltip: ComputedRef<string>
  happinessTooltip: ComputedRef<string>
  capsTooltip: ComputedRef<string>
}

// The header renders these as Tailwind text classes, so the strings stay local
// (getHappinessColor returns theme CSS vars); the >=75/50/25 banding is canonical.
const HAPPINESS_TEXT_CLASS: Record<HappinessLevel, string> = {
  high: 'text-terminal-green',
  medium: 'text-green-400',
  low: 'text-yellow-400',
  critical: 'text-red-500',
}
const HAPPINESS_MORALE_TEXT: Record<HappinessLevel, string> = {
  high: '😊 Excellent morale!',
  medium: '😐 Acceptable morale',
  low: '😟 Low morale - needs attention',
  critical: '😢 Critical - dwellers are unhappy!',
}

/**
 * Route-aware vault hydration for the shell header.
 *
 * The route decides what the header shows: `vault` is always `loadedVaults[id]`
 * for the CURRENT route's id, never the store's remembered `activeVaultId`.
 * Safe to call from multiple component instances — every side effect is
 * idempotent and `ensureVaultLoaded` dedupes concurrent loads.
 */
export function useVaultHeaderContext(): VaultHeaderContext {
  const route = useRoute()
  const authStore = useAuthStore()
  const vaultStore = useVaultStore()

  const loadFailed = ref(false)

  // A vault route is any path under /vault/ that carries a vault id param.
  // Bare truthiness of route.params.id is NOT enough: /dweller/:id/chat also
  // has an `id` param, but that is a dweller id — hydrating from it would
  // request the wrong resource.
  const isVaultRoute = computed(() => {
    const id = route.params.id
    return route.path.startsWith('/vault/') && typeof id === 'string' && id.length > 0
  })

  const vaultId = computed<string | null>(() => {
    if (!isVaultRoute.value) return null
    const id = route.params.id
    return typeof id === 'string' && id.length > 0 ? id : null
  })

  const vault = computed<VaultWithNumbers | null>(() => {
    const id = vaultId.value
    return id ? (vaultStore.loadedVaults[id] ?? null) : null
  })

  // "Do not render false zeros" gate: the header shows a loading affordance
  // while on a vault route before the vault has actually loaded.
  const isReady = computed(() => isVaultRoute.value && vault.value !== null)

  const dwellersCount = computed(() => vault.value?.dweller_count ?? 0)
  const populationMax = computed(() => vault.value?.population_max ?? 0)
  const populationUtilization = computed(() => {
    const max = populationMax.value
    const current = dwellersCount.value

    // Avoid division by zero
    if (!max || max === 0) return 0

    return (current / max) * 100
  })
  const populationColor = computed(() => {
    if (populationUtilization.value >= 90) return 'text-red-500'
    if (populationUtilization.value >= 75) return 'text-yellow-400'
    return 'text-terminal-green'
  })

  const happiness = computed(() => vault.value?.happiness ?? 0)
  const happinessColor = computed(() => HAPPINESS_TEXT_CLASS[getHappinessLevel(happiness.value)])

  const energy = computed(() => ({
    current: vault.value?.power ?? 0,
    max: vault.value?.power_max ?? 100,
  }))
  const food = computed(() => ({
    current: vault.value?.food ?? 0,
    max: vault.value?.food_max ?? 100,
  }))
  const water = computed(() => ({
    current: vault.value?.water ?? 0,
    max: vault.value?.water_max ?? 100,
  }))
  const resourceRates = computed<ResourceRates | undefined>(() => {
    const id = vaultId.value
    return id ? vaultStore.resourceRates[id] : undefined
  })
  const bottleCaps = computed(() => vault.value?.bottle_caps ?? 0)
  const dwellersTooltip = computed(
    () =>
      `Total dwellers in vault: ${dwellersCount.value}/${populationMax.value}\nCapacity: ${populationMax.value} dwellers`
  )
  const happinessTooltip = computed(
    () =>
      `Vault Happiness: ${happiness.value}%\n${HAPPINESS_MORALE_TEXT[getHappinessLevel(happiness.value)]}`
  )
  const capsTooltip = computed(
    () => `Bottle Caps: ${bottleCaps.value}\nVault currency for construction and upgrades`
  )

  // Hydrate the vault for the current route. Fires only when both a vault id
  // and a token exist; a missing either means "do nothing" — no request.
  // ensureVaultLoaded is idempotent (cached vaults skip the GET, concurrent
  // calls dedupe), so a second composable instance cannot trigger a duplicate
  // request. A rejection is swallowed into loadFailed so an unhandled promise
  // in a watcher cannot break unrelated views.
  watch(
    [vaultId, () => authStore.token],
    ([id, token]) => {
      loadFailed.value = false
      if (!id || !token) return
      void vaultStore.ensureVaultLoaded(id, token).catch(() => {
        if (vaultId.value === id && authStore.token === token) {
          loadFailed.value = true
        }
      })
    },
    { immediate: true }
  )

  // Leaving vault routes entirely hands the tick stream lifecycle back to the
  // shell: stop polling so a background tick cannot keep a stale vault alive.
  watch(vaultId, (id) => {
    if (!id) {
      vaultStore.stopResourcePolling()
    }
  })

  return {
    isVaultRoute,
    vaultId,
    vault,
    isReady,
    loadFailed,
    dwellersCount,
    populationMax,
    populationUtilization,
    populationColor,
    happiness,
    happinessColor,
    energy,
    food,
    water,
    resourceRates,
    bottleCaps,
    dwellersTooltip,
    happinessTooltip,
    capsTooltip,
  }
}
