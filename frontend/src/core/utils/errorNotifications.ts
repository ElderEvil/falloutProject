// Share notification ownership without coupling the HTTP client to store/UI helpers.
const notifiedErrors = new WeakSet<object>()

export function claimErrorNotification(error: unknown): boolean {
  const chain: object[] = []
  let cause = error
  while (cause !== null && typeof cause === 'object' && !chain.includes(cause)) {
    if (notifiedErrors.has(cause)) return false
    chain.push(cause)
    cause = 'cause' in cause ? cause.cause : undefined
  }
  chain.forEach((failure) => notifiedErrors.add(failure))
  return true
}
