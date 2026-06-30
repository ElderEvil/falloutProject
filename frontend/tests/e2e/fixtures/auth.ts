import type { Page } from '@playwright/test'

export interface TestUser {
  id: string
  email: string
  is_active: boolean
  is_superuser: boolean
}

export const TEST_USER: TestUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  is_active: true,
  is_superuser: true,
}

/**
 * Set auth token and user data in localStorage to simulate a logged-in state.
 * The auth store (useAuthStore) reads from localStorage keys 'token' and 'user'.
 */
export async function setAuthToken(page: Page, token: string, user: TestUser = TEST_USER) {
  await page.evaluate(
    ({ token, user }) => {
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    { token, user }
  )
}
