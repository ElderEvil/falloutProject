import { computed, effectScope } from 'vue'
import { useDocumentVisibility, useEventListener, useLocalStorage, useOnline } from '@vueuse/core'
import { AUTH_SESSION_EXPIRED_EVENT } from '@/core/utils/authSessionEvents'

/** Own listeners explicitly: store actions can create subscriptions outside a component scope. */
export function useBackgroundActivity(authenticated = true) {
  const scope = effectScope()
  const canRun = scope.run(() => {
    const visibility = useDocumentVisibility()
    const online = useOnline()
    const token = useLocalStorage<string | null>('token', null)
    useEventListener(window, AUTH_SESSION_EXPIRED_EVENT, () => {
      token.value = null
    })
    return computed(
      () => visibility.value === 'visible' && online.value && (!authenticated || !!token.value)
    )
  })!
  return { canRun, stop: () => scope.stop() }
}
