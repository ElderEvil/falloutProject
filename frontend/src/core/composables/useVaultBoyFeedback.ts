import { computed, ref } from 'vue'
import type { VaultBoyAnimationId } from '@/core/utils/vaultBoyAnimations'

export interface VaultBoyFeedbackEvent {
  animation: VaultBoyAnimationId
  title: string
  message: string
  vaultId: string
  /** Optional keys limit repeated warnings and celebrations. */
  key?: string
}

const queue = ref<(VaultBoyFeedbackEvent & { id: number })[]>([])
const lastShown = new Map<string, number>()
let nextId = 0
export const VAULT_BOY_FEEDBACK_MS = 4200

export function useVaultBoyFeedback() {
  function show(event: VaultBoyFeedbackEvent, { priority = false }: { priority?: boolean } = {}) {
    if (event.key) {
      const key = `${event.vaultId}:${event.key}`
      const previous = lastShown.get(key)
      if (previous !== undefined && Date.now() - previous < 30000) return
      lastShown.set(key, Date.now())
    }
    // Preserve the current animation and keep queued feedback fresh during event bursts.
    if (queue.value.length >= 4) queue.value.splice(1, 1)
    const entry = { ...event, id: ++nextId }
    if (priority) queue.value.unshift(entry)
    else queue.value.push(entry)
  }
  const dismiss = () => {
    queue.value.shift()
  }
  const clear = () => {
    queue.value = []
    lastShown.clear()
  }
  return { current: computed(() => queue.value[0] ?? null), show, dismiss, clear }
}
