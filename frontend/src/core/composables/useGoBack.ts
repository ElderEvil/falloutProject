import { useRoute, useRouter } from 'vue-router'

/**
 * Replaces `:param` placeholders in a path with actual values from route params.
 *
 * @example
 * interpolate('/vault/:id/dwellers', { id: '123' }) // '/vault/123/dwellers'
 */
function interpolate(path: string, params: Record<string, string | string[]>): string {
  return path.replace(/:(\w+)/g, (_, key: string) => {
    const value = params[key]
    if (value === undefined) return ''
    return Array.isArray(value) ? value[0] : value
  })
}

/**
 * Composable for browser-history-aware back navigation.
 *
 * - If there is browser history (`window.history.length > 1`), calls `router.back()`.
 * - Otherwise, falls back to `router.push(meta.parentRoute)` if the current route
 *   defines `meta.parentRoute` (with `:param` interpolation from current route params).
 * - If no `parentRoute` is defined, falls back to `router.push('/')`.
 *
 * @returns `{ goBack }` — call `goBack()` from a back button handler.
 */
export function useGoBack() {
  const router = useRouter()
  const route = useRoute()

  const goBack = (): void => {
    if (window.history.length > 1 && window.history.state?.back !== undefined) {
      router.back()
      return
    }

    const parentRoute = route.meta?.parentRoute
    if (typeof parentRoute === 'string') {
      router.replace(interpolate(parentRoute, route.params))
      return
    }

    router.replace('/')
  }

  return { goBack }
}
