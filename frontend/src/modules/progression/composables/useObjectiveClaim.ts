import { ref, type Ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import { useSound } from '@/core/composables/useSound'
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
  const { playSound } = useSound()
  const claiming = ref(false)
  const error = ref<string | null>(null)

  function refreshAfterClaim(id: string): void {
    void objectivesStore
      .fetchObjectives(id)
      .catch((err) => handleStoreError(err, 'Failed to refresh objective guidance'))
    if (!auth.token) return
    void vaultStore
      .refreshVault(id, auth.token)
      .catch((err) => handleStoreError(err, 'Failed to refresh claimed rewards'))
    // A claim can grant a dweller; the local roster feeds the wasteland picker.
    void dwellerStore.filter
      .fetchDwellersByVault(id, auth.token)
      .catch((err) => handleStoreError(err, 'Failed to refresh the dweller roster'))
  }

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
      playSound('objectiveClaim')
      onClaimed?.(claimed)
    } catch (err) {
      if (vaultId.value === id) error.value = getErrorMessage(err)
      return
    } finally {
      claiming.value = false
    }
    refreshAfterClaim(id)
  }

  async function claimAll(objectiveIds: string[]): Promise<number> {
    const id = vaultId.value
    if (!id || claiming.value || objectiveIds.length === 0) return 0
    claiming.value = true
    error.value = null
    let claimedCount = 0
    try {
      for (const objectiveId of objectiveIds) {
        if (vaultId.value !== id) break
        await objectivesStore.completeObjective(id, objectiveId)
        claimedCount += 1
      }
    } catch (err) {
      if (vaultId.value === id) error.value = getErrorMessage(err)
    } finally {
      claiming.value = false
    }
    if (vaultId.value !== id) return 0
    if (claimedCount > 0) {
      playSound('objectiveClaim')
      refreshAfterClaim(id)
    }
    return claimedCount
  }

  const clearError = (): void => {
    error.value = null
  }

  return { claiming, error, claim, claimAll, clearError }
}
