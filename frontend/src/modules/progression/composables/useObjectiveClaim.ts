import { ref, type Ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import { useObjectivesStore } from '../stores/objectives'
import type { Objective } from '../models/objective'

/** Shared owner-claim flow: guard, request, guidance refresh, pending state and
 * error handling. Callers pass their own success feedback via `onClaimed` so the
 * toast/modal stays local. */
export function useObjectiveClaim(vaultId: Ref<string | null>) {
  const objectivesStore = useObjectivesStore()
  const vaultStore = useVaultStore()
  const dwellerStore = useDwellerStore()
  const auth = useAuthStore()
  const claiming = ref(false)
  const error = ref<string | null>(null)

  async function claim(
    objectiveId: string,
    onClaimed?: (claimed: Objective) => void
  ): Promise<void> {
    const id = vaultId.value
    if (!id || claiming.value) return
    claiming.value = true
    error.value = null
    try {
      const claimed = await objectivesStore.completeObjective(id, objectiveId)
      if (vaultId.value !== id) return
      onClaimed?.(claimed)
      void objectivesStore
        .fetchObjectives(vaultId.value)
        .catch((err) => handleStoreError(err, 'Failed to refresh objective guidance'))
    } catch (err) {
      if (vaultId.value === id) error.value = getErrorMessage(err)
      return
    } finally {
      claiming.value = false
    }
    if (auth.token) {
      void vaultStore
        .refreshVault(id, auth.token)
        .catch((err) => handleStoreError(err, 'Failed to refresh claimed rewards'))
      // A claim can grant a dweller; the local roster feeds the wasteland picker.
      void dwellerStore.filter
        .fetchDwellersByVault(id, auth.token)
        .catch((err) => handleStoreError(err, 'Failed to refresh the dweller roster'))
    }
  }

  return { claiming, error, claim }
}
