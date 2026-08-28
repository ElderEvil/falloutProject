import { type Ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '../stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'

interface RunOptions {
  flag?: Ref<boolean>
  errorMessage?: string
  refreshVault?: boolean
  onSuccess?: () => void
}

// Glue only: run a store action, refetch the dweller detail (and optionally the
// vault), surface failures as a toast. Domain logic stays in the container.
export function useDwellerDetailActions(dwellerId: Ref<string>, vaultId: Ref<string>) {
  const authStore = useAuthStore()
  const { filter: dwellerStore } = useDwellerStore()
  const vaultStore = useVaultStore()
  const toast = useToast()

  const refetch = () => dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)

  const runAction = async (action: () => Promise<unknown>, opts: RunOptions = {}) => {
    if (!dwellerStore.detailedDwellers[dwellerId.value] || opts.flag?.value) return
    if (opts.flag) opts.flag.value = true
    try {
      await action()
      await refetch()
      if (opts.refreshVault) await vaultStore.refreshVault(vaultId.value, authStore.token as string)
      opts.onSuccess?.()
    } catch {
      toast.error(opts.errorMessage ?? 'Action failed')
    } finally {
      if (opts.flag) opts.flag.value = false
    }
  }

  return { refetch, runAction }
}
