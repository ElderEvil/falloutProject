import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import VerifyEmailView from '@/modules/auth/views/VerifyEmailView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { authService } from '@/modules/auth/services/authService'

vi.mock('@/modules/auth/services/authService', () => ({
  authService: {
    verifyEmail: vi.fn(),
    resendVerificationEmail: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}))

const TOKEN = 'verification-token-123'

describe('VerifyEmailView', () => {
  let router: ReturnType<typeof createRouter>
  let authStore: ReturnType<typeof useAuthStore>

  async function mountView(path = '/verify-email') {
    await router.push(path)
    await router.isReady()
    return mount(VerifyEmailView, {
      global: { plugins: [router] },
    })
  }

  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    authStore = useAuthStore()
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/login', component: { template: '<div>Login</div>' } },
        { path: '/verify-email', component: VerifyEmailView },
      ],
    })
    vi.mocked(authService.verifyEmail).mockReset()
    vi.mocked(authService.resendVerificationEmail).mockReset()
    vi.mocked(authService.getCurrentUser).mockReset()
  })

  it('sends the query token through the store and routes to / when authenticated', async () => {
    authStore.token = 'session-token'
    authStore.user = { id: '1', username: 'Overseer', email: 'o@vault.com', email_verified: false }
    vi.mocked(authService.verifyEmail).mockResolvedValue({ data: { msg: 'Email verified' } })
    vi.mocked(authService.getCurrentUser).mockResolvedValue({
      data: { id: '1', username: 'Overseer', email: 'o@vault.com', email_verified: true },
    })

    const wrapper = await mountView(`/verify-email?token=${TOKEN}`)
    await flushPromises()

    expect(authService.verifyEmail).toHaveBeenCalledWith(TOKEN)
    expect(authService.getCurrentUser).toHaveBeenCalled()
    expect(authStore.user?.email_verified).toBe(true)
    expect(router.currentRoute.value.path).toBe('/')
    expect(wrapper.text()).toContain('VERIFICATION SUCCESSFUL')
  })

  it('routes to /login when anonymous', async () => {
    vi.mocked(authService.verifyEmail).mockResolvedValue({ data: { msg: 'Email verified' } })

    await mountView(`/verify-email?token=${TOKEN}`)
    await flushPromises()

    expect(authService.verifyEmail).toHaveBeenCalledWith(TOKEN)
    expect(authService.getCurrentUser).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('offers a resend action on failure for authenticated unverified users', async () => {
    authStore.token = 'session-token'
    authStore.user = { id: '1', username: 'Overseer', email: 'o@vault.com', email_verified: false }
    vi.mocked(authService.verifyEmail).mockRejectedValue(new Error('Invalid token'))
    vi.mocked(authService.resendVerificationEmail).mockResolvedValue({ data: { msg: 'sent' } })

    const wrapper = await mountView(`/verify-email?token=${TOKEN}`)
    await flushPromises()

    expect(wrapper.text()).toContain('RETURN TO LOGIN')
    const resend = wrapper.findAll('button').find((button) => button.text().includes('RESEND'))
    expect(resend?.exists()).toBe(true)

    await resend?.trigger('click')
    await flushPromises()

    expect(authService.resendVerificationEmail).toHaveBeenCalledTimes(1)
  })

  it('does not offer a resend action on failure when anonymous', async () => {
    vi.mocked(authService.verifyEmail).mockRejectedValue(new Error('Invalid token'))

    const wrapper = await mountView(`/verify-email?token=${TOKEN}`)
    await flushPromises()

    expect(wrapper.text()).toContain('RETURN TO LOGIN')
    expect(wrapper.text()).not.toContain('RESEND')
  })

  it('rejects a missing token without calling the API', async () => {
    const wrapper = await mountView('/verify-email')
    await flushPromises()

    expect(authService.verifyEmail).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Invalid or missing verification token')
  })
})
