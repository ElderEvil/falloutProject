import { QueryCache, QueryClient } from '@tanstack/vue-query'
import { getErrorMessage } from '@/core/utils/errorHandler'

/**
 * Build the project's QueryClient.
 *
 * Server-state errors are logged once here, with a generic context supplied by
 * the query's `meta.errorContext`. Keep this module free of feature imports:
 * `core/**` must never depend on `@/modules/**`.
 *
 * The factory is exported so tests can build a client with the same logging
 * behaviour as production; `queryClient` is the single app instance.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        const context = query.meta?.errorContext
        const label = typeof context === 'string' ? context : 'Query failed'
        console.warn(`${label}: ${getErrorMessage(error)}`)
      },
    }),
  })
}

export const queryClient = createQueryClient()
