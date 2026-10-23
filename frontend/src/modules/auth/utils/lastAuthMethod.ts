export type AuthMethod = 'password' | 'google' | 'github'

const STORAGE_KEY = 'auth_last_method'

export function getLastAuthMethod(): AuthMethod | null {
  if (typeof window === 'undefined') return null
  const value = window.localStorage.getItem(STORAGE_KEY)
  return value === 'password' || value === 'google' || value === 'github' ? value : null
}

export function setLastAuthMethod(method: AuthMethod): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, method)
}
