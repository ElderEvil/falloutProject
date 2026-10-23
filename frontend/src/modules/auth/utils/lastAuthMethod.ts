export type AuthMethod = 'password' | 'google' | 'github'

const STORAGE_KEY = 'auth_last_method'

export function getLastAuthMethod(): AuthMethod | null {
  if (typeof window === 'undefined') return null
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value === 'password' || value === 'google' || value === 'github' ? value : null
  } catch {
    return null
  }
}

export function setLastAuthMethod(method: AuthMethod): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, method)
  } catch {
    // Storage can be blocked or full; the hint is non-critical.
  }
}
