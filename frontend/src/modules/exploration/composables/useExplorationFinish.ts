import { ref, toValue, type MaybeRefOrGetter } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'
import { useExplorationStore, type RewardsSummary } from '../stores/exploration'

export type ExplorationFinishAction = (
  explorationId: string,
  token: string
) => Promise<{ rewards_summary?: RewardsSummary | null }>

export interface FinishExplorationOptions {
  /** Display name override when the caller already resolved it (e.g. from detailed dwellers). */
  dwellerName?: string
  /** Runs after the action settles, before the vault/dweller refresh. */
  onFinished?: (dwellerId: string) => void
}

export function useExplorationFinish(vaultId?: MaybeRefOrGetter<string | undefined>) {
  const authStore = useAuthStore()
  const { filter: dwellerStore } = useDwellerStore()
  const vaultStore = useVaultStore()
  const explorationStore = useExplorationStore()
  const toast = useToast()

  const showRewardsModal = ref(false)
  const completedExplorationRewards = ref<RewardsSummary | null>(null)
  const completedDwellerName = ref('')
  const completedExplorationId = ref('')
  const rewardsDirty = ref(false)

  function openRewards(rewards: RewardsSummary, dwellerName: string, explorationId: string): void {
    completedExplorationRewards.value = rewards
    completedDwellerName.value = dwellerName
    completedExplorationId.value = explorationId
    showRewardsModal.value = true
  }

  function resetRewards(): void {
    showRewardsModal.value = false
    completedExplorationRewards.value = null
    completedDwellerName.value = ''
    completedExplorationId.value = ''
  }

  /** Refresh the vault after overflow loot was resolved. False means the caller should keep the modal open. */
  async function refreshIfDirty(): Promise<boolean> {
    const vault = toValue(vaultId)
    if (!rewardsDirty.value || !vault || !authStore.token) return true
    try {
      await vaultStore.refreshVault(vault, authStore.token)
      rewardsDirty.value = false
      return true
    } catch {
      toast.error('Failed to refresh vault rewards')
      return false
    }
  }

  async function finishExploration(
    explorationId: string,
    action: ExplorationFinishAction,
    errorMessage: string,
    options: FinishExplorationOptions = {}
  ): Promise<void> {
    if (!authStore.token) return
    const exploration =
      explorationStore.activeExplorations[explorationId] ??
      explorationStore.explorations.find((e) => e.id === explorationId)
    if (!exploration) return

    try {
      const result = await action(explorationId, authStore.token)

      if (result?.rewards_summary) {
        const dweller = dwellerStore.dwellers.find((d) => d.id === exploration.dweller_id)
        const dwellerName =
          options.dwellerName ??
          (dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Dweller')
        explorationStore.acknowledgeSseReward(exploration.dweller_id)
        openRewards(result.rewards_summary, dwellerName, explorationId)
      }

      options.onFinished?.(exploration.dweller_id)

      const vault = toValue(vaultId)
      if (vault) {
        await vaultStore.refreshVault(vault, authStore.token)
        await dwellerStore.fetchDwellersByVault(vault, authStore.token)
      }
    } catch {
      toast.error(errorMessage)
    }
  }

  return {
    showRewardsModal,
    completedExplorationRewards,
    completedDwellerName,
    completedExplorationId,
    rewardsDirty,
    openRewards,
    resetRewards,
    refreshIfDirty,
    finishExploration,
  }
}
