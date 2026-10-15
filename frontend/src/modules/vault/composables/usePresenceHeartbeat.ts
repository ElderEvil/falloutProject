import { onMounted, onUnmounted } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { useVaultStore } from '../stores/vault'

/** Heartbeat proving a watching player: pings only while the vault overview is visible. */
export function usePresenceHeartbeat(
  getVaultId: () => string | null,
  getToken: () => string | null,
  intervalMs = 30_000
): void {
  const vaultStore = useVaultStore()

  const ping = (): void => {
    const vaultId = getVaultId()
    const token = getToken()
    if (vaultId && token && document.visibilityState === 'visible')
      void vaultStore.pingPresence(vaultId, token)
  }
  const onVisibilityChange = (): void => {
    if (document.visibilityState === 'visible') ping()
  }

  const { pause } = useIntervalFn(ping, intervalMs, { immediateCallback: true })

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibilityChange)
  })
  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    pause()
  })
}
