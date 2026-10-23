import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import OAuthCallbackView from '@/modules/auth/views/OAuthCallbackView.vue'
import AuthTerminalFrame from '@/modules/auth/components/AuthTerminalFrame.vue'
import { oauthService } from '@/modules/auth/services/oauthService'
import { useAuthStore } from '@/modules/auth/stores/auth'

vi.mock('@/modules/auth/services/oauthService', () => ({
  oauthService: { redeemHandoff: vi.fn() },
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>Home</div>' } },
      { path: '/auth/callback', component: OAuthCallbackView },
      { path: '/login', component: { template: '<div>Login</div>' } },
    ],
  })
}

describe('OAuthCallbackView', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.mocked(oauthService.redeemHandoff).mockReset()
  })

  it('redeems the code, stores the provider hint, and redirects home', async () => {
    vi.mocked(oauthService.redeemHandoff).mockResolvedValue({
      data: { access_token: 'access', refresh_token: 'refresh' },
    } as never)
    const router = makeRouter()
    await router.push('/auth/callback?code=abc&provider=github')
    await router.isReady()
    const store = useAuthStore()
    const loginWithTokens = vi.spyOn(store, 'loginWithTokens').mockResolvedValue(true)

    mount(OAuthCallbackView, { global: { plugins: [router] } })
    await flushPromises()

    expect(oauthService.redeemHandoff).toHaveBeenCalledWith('abc')
    expect(loginWithTokens).toHaveBeenCalledWith({ access_token: 'access', refresh_token: 'refresh' })
    expect(localStorage.getItem('auth_last_method')).toBe('github')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('shows a controlled message for a cancelled sign-in', async () => {
    const router = makeRouter()
    await router.push('/auth/callback?error=access_denied')
    await router.isReady()

    const wrapper = mount(OAuthCallbackView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.findComponent(AuthTerminalFrame).props('error')).toContain('cancelled')
    expect(oauthService.redeemHandoff).not.toHaveBeenCalled()
  })
})
