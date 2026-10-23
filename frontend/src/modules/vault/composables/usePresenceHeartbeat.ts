import { usePolling } from '@/core/composables/usePolling'
import { useVaultStore } from '../stores/vault'

/** Heartbeat proving a watching player: pings only while the vault overview is visible. */
export function usePresenceHeartbeat(
  getVaultId: () => string | null,
  getToken: () => string | null,
  intervalMs = 30_000
): void {
  const vaultStore = useVaultStore()

  const ping = () => {
    const vaultId = getVaultId()
    const token = getToken()
    if (vaultId && token && document.visibilityState === 'visible')
      return vaultStore.pingPresence(vaultId, token)
  }
  usePolling(ping, { interval: intervalMs })
}
