import { computed, ref } from 'vue'
import { useToast } from './useToast'
import { getErrorMessage } from '@/core/types/utils'
import { handleStoreError } from '@/core/utils/errorHandler'

export interface AsyncActionOptions {
  /** Re-throw after the error has been recorded and surfaced. */
  rethrow?: boolean
  /** Show the extracted error to the user. Enabled by default. */
  showToast?: boolean
  /** Context used by the shared error handler. */
  context?: string
}

/**
 * Standard loading/error handling for single async operations.
 *
 * Operations that require a per-key loading map or a concurrency counter stay
 * bespoke; forcing those into one boolean would lose state and regress UI.
 */
export function useAsyncAction<Args extends unknown[], Result>(
  action: (...args: Args) => Promise<Result>,
  { rethrow = false, showToast = true, context = 'Request failed' }: AsyncActionOptions = {}
) {
  const pendingCount = ref(0)
  const error = ref<string | null>(null)
  const toast = useToast()
  const isLoading = computed(() => pendingCount.value > 0)

  async function run(...args: Args): Promise<Result | null> {
    pendingCount.value++
    error.value = null

    try {
      return await action(...args)
    } catch (caught: unknown) {
      const message = getErrorMessage(caught)
      error.value = message
      handleStoreError(caught, context, !showToast)
      if (showToast) toast.error(message)
      if (rethrow) throw caught
      return null
    } finally {
      pendingCount.value--
    }
  }

  return { run, isLoading, error }
}
