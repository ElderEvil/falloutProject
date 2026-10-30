import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConnectedAccountsCard from '@/modules/profile/components/ConnectedAccountsCard.vue'
import { oauthService } from '@/modules/auth/services/oauthService'

vi.mock('@/modules/auth/services/oauthService', () => ({
  oauthService: {
    getProviders: vi.fn(),
    getLinkedAccounts: vi.fn(),
    linkProvider: vi.fn(),
    unlinkProvider: vi.fn(),
  },
}))

const toast = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
}))
vi.mock('@/core/composables/useToast', () => ({ useToast: () => toast }))

async function mountCard(navigate?: (url: string) => void) {
  const wrapper = mount(ConnectedAccountsCard, {
    props: navigate ? { navigate } : undefined,
  })
  await flushPromises()
  return wrapper
}

const row = (wrapper: ReturnType<typeof mount>, provider: 'google' | 'github') =>
  wrapper.get(`[data-testid="connected-${provider}"]`)

describe('ConnectedAccountsCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(oauthService.getProviders).mockResolvedValue({ google: true, github: true })
    vi.mocked(oauthService.getLinkedAccounts).mockResolvedValue({
      providers: ['google'],
      has_password: false,
    })
    vi.mocked(oauthService.linkProvider).mockReset()
    vi.mocked(oauthService.unlinkProvider).mockReset()
    toast.success.mockReset()
    toast.error.mockReset()
  })

  it('shows linked and unlinked providers and protects the only sign-in method', async () => {
    const wrapper = await mountCard()

    expect(row(wrapper, 'google').text()).toContain('CONNECTED')
    expect(row(wrapper, 'github').text()).toContain('NOT CONNECTED')
    expect(wrapper.text()).toContain('This is your only sign-in method')
    const unlink = row(wrapper, 'google')
      .findAll('button')
      .find((button) => button.text() === 'DISCONNECT')
    expect(unlink?.attributes('disabled')).toBeDefined()
  })

  it('requires confirmation before unlinking and updates the row', async () => {
    vi.mocked(oauthService.getLinkedAccounts).mockResolvedValue({
      providers: ['google'],
      has_password: true,
    })
    vi.mocked(oauthService.unlinkProvider).mockResolvedValue()
    const wrapper = await mountCard()

    await row(wrapper, 'google')
      .findAll('button')
      .find((button) => button.text() === 'DISCONNECT')!
      .trigger('click')
    expect(row(wrapper, 'google').text()).toContain('DISCONNECT?')

    await row(wrapper, 'google')
      .findAll('button')
      .find((button) => button.text() === 'CONFIRM')!
      .trigger('click')
    await flushPromises()

    expect(oauthService.unlinkProvider).toHaveBeenCalledWith('google')
    expect(row(wrapper, 'google').text()).toContain('NOT CONNECTED')
    expect(toast.success).toHaveBeenCalled()
  })

  it('starts a provider link and navigates to the authorize URL', async () => {
    vi.mocked(oauthService.linkProvider).mockResolvedValue({
      authorize_url: 'https://provider.example/authorize',
    })
    const assign = vi.fn()
    const wrapper = await mountCard(assign)

    await row(wrapper, 'github')
      .findAll('button')
      .find((button) => button.text() === 'CONNECT')!
      .trigger('click')
    await flushPromises()

    expect(oauthService.linkProvider).toHaveBeenCalledWith('github')
    expect(assign).toHaveBeenCalledWith('https://provider.example/authorize')
  })
})
