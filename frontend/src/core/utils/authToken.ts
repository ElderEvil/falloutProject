/**
 * Late-bound access to the current auth token for infrastructure that cannot
 * import the auth store (SSE setup), avoiding a vault <-> auth import cycle.
 * The auth store registers the provider when it initializes.
 */
let provider: () => string | null = () => null

export function setAuthTokenProvider(read: () => string | null): void {
  provider = read
}

export function getAuthToken(): string | null {
  return provider()
}
