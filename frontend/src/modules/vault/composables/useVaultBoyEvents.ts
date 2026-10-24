import { watch, type Ref } from 'vue'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import { useToast } from '@/core/composables/useToast'
import { useStorageStore } from '@/modules/storage/stores/storage'
import { getHappinessLevel } from '@/modules/dwellers/models/dweller'
import { useVaultStore } from '../stores/vault'

/** Animate state transitions once; unchanged low/full states do not replay every tick. */
export function useVaultBoyEvents(vaultId: Ref<string>) {
  const vaultStore = useVaultStore()
  const storage = useStorageStore()
  const feedback = useVaultBoyFeedback()
  const toast = useToast()

  watch(
    () => {
      const vault = vaultStore.activeVault
      if (!vaultId.value || vaultStore.activeVaultId !== vaultId.value || !vault) return null
      const level = getHappinessLevel(vault.happiness)
      return level === 'low' || level === 'critical' ? vaultId.value : null
    },
    (id) => {
      if (!id) return
      const message = 'Dwellers are unhappy. Check food, water, and room assignments.'
      feedback.show({
        animation: 'happiness-low',
        title: 'Happiness is low',
        message,
        vaultId: id,
        key: 'happiness-low',
      })
      toast.warning(message)
    },
    { immediate: true }
  )

  watch(
    () =>
      storage.vaultId === vaultId.value &&
      storage.space &&
      storage.space.max_space > 0 &&
      storage.space.available_space <= 0
        ? vaultId.value
        : null,
    (id) => {
      if (!id) return
      const message = 'Build or upgrade storage, or sell items to make room.'
      feedback.show({
        animation: 'storage',
        title: 'Storage full',
        message,
        vaultId: id,
        key: 'storage-full',
      })
      toast.warning(message)
    },
    { immediate: true }
  )
}
