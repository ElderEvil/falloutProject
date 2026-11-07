import type { Ref } from 'vue'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { setRadioMode } from '@/modules/radio/api/radio'
import { useVaultStore } from '../stores/vault'

/**
 * Switch a vault's radio into happiness mode.
 *
 * Shared by the dwellers dashboard and the happiness view so the radio action
 * and its loading state stay identical in both entry points.
 */
export function useActivateRadio(vaultId: Ref<string>) {
  const authStore = useAuthStore()
  const vaultStore = useVaultStore()

  const { run, isLoading: isActivatingRadio } = useAsyncAction(
    async (currentVaultId: string, token: string) => {
      await setRadioMode(currentVaultId, 'happiness')
      await vaultStore.refreshVault(currentVaultId, token)
    },
    { context: 'Failed to activate radio mode' }
  )

  const handleActivateRadio = async () => {
    if (!vaultId.value || !authStore.token || isActivatingRadio.value) return
    await run(vaultId.value, authStore.token)
  }

  return { isActivatingRadio, handleActivateRadio }
}
