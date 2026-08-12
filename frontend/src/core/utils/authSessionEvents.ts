export interface RefreshedAuthTokens {
  token: string
  refreshToken?: string
}

export const AUTH_TOKENS_REFRESHED_EVENT = 'auth-tokens-refreshed'

export function dispatchRefreshedAuthTokens(tokens: RefreshedAuthTokens): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent<RefreshedAuthTokens>(AUTH_TOKENS_REFRESHED_EVENT, { detail: tokens }))
}
