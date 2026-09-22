import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../helpers/mountWithSetup'
import HappinessView from '@/modules/vault/views/HappinessView.vue'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'vault-1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } }),
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }),
}))

// The auth store auto-fetches the user when a token exists; resolve it so the
// store keeps the token instead of logging out on the real (unavailable) API.
vi.mock('@/modules/auth/services/authService', () => ({
  authService: {
    getCurrentUser: vi.fn().mockResolvedValue({
      data: { id: 'user-1', username: 'overseer', is_superuser: true },
    }),
    logout: vi.fn().mockResolvedValue({}),
    refreshToken: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
  },
}))

const vault = {
  id: 'vault-1',
  number: 1,
  happiness: 80,
  dweller_count: 5,
  power: 100,
  power_max: 100,
  food: 100,
  food_max: 100,
  water: 100,
  water_max: 100,
  radio_mode: 'off',
}

describe('HappinessView', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    vi.mocked(axios.get).mockImplementation((url: string) => {
      if (url.includes('/incidents')) return Promise.resolve({ data: { incidents: [] } })
      if (url.includes('/dwellers')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: vault })
    })
  })

  it('renders the happiness dashboard once data loads', async () => {
    const wrapper = mountWithSetup(HappinessView, {
      global: { stubs: { SidePanel: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Vault Happiness')
    expect(wrapper.text()).toContain('80%')
    expect(wrapper.text()).toContain('EXCELLENT')
  })

  it('shows the error state and recovers via Retry', async () => {
    vi.mocked(axios.get).mockRejectedValueOnce(new Error('boom'))

    const wrapper = mountWithSetup(HappinessView, {
      global: { stubs: { SidePanel: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Error Loading Data')

    const retry = wrapper.findAll('button').find((b) => b.text().includes('Retry'))
    expect(retry).toBeTruthy()
    await retry!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('EXCELLENT')
  })
})