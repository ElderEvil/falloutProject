import { computed } from 'vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerFilterStore } from '../stores/dwellerFilter'

/** Room occupancy source: the active vault's roster, else the filtered page. */
export function useVaultRoster() {
  const filter = useDwellerFilterStore()
  const vaultStore = useVaultStore()
  return computed(() => {
    const loadedVaultId = filter.allDwellersLoadedVaultId
    const activeVaultId = vaultStore.activeVaultId
    return loadedVaultId && (!activeVaultId || activeVaultId === loadedVaultId)
      ? filter.allDwellers
      : filter.dwellers
  })
}
