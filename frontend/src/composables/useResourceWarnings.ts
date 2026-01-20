import { ref, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { useVaultStore } from '@/stores/vault'

interface WarningState {
  lastShown: number
}

const WARNING_COOLDOWN = 30000 // 30 seconds

export function useResourceWarnings() {
  const toast = useToast()
  const vaultStore = useVaultStore()
  
  const warningStates = ref<Record<string, WarningState>>({})

  watch(() => vaultStore.activeVault, (vault) => {
    if (!vault?.resource_warnings) return

    const now = Date.now()

    vault.resource_warnings.forEach((warning) => {
      const lastState = warningStates.value[warning.type]
      
      if (!lastState || (now - lastState.lastShown > WARNING_COOLDOWN)) {
        const isCritical = warning.type.startsWith('critical_')
        
        toast.add({
          message: warning.message,
          variant: isCritical ? 'error' : 'warning',
          duration: isCritical ? 0 : 5000 // Critical warnings don't auto-dismiss
        })

        warningStates.value[warning.type] = {
          lastShown: now
        }
      }
    })
  }, { deep: true })
}
