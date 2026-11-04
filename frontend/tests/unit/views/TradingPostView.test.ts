import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createRouterMock, createToastMock } from '../helpers/mocks'
import { flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../helpers/mountWithSetup'
import TradingPostView from '@/modules/trading/views/TradingPostView.vue'
import { tradingService } from '@/modules/trading/services/tradingService'
import type { TradeMarketResponse } from '@/modules/trading/models/trading'

const mockToast = createToastMock()

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))
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
vi.mock('@/modules/trading/services/tradingService', () => ({
  tradingService: { getMarket: vi.fn(), sellDweller: vi.fn(), buyDweller: vi.fn() },
}))

const market = (): TradeMarketResponse => ({
  market_offers: [],
  my_listings: [],
  bottle_caps: 500,
})

describe('TradingPostView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    vi.mocked(tradingService.getMarket).mockResolvedValue(market())
  })

  it('renders the dweller market for the routed vault', async () => {
    const wrapper = mountWithSetup(TradingPostView, { global: { stubs: { SidePanel: true } } })
    await flushPromises()

    expect(tradingService.getMarket).toHaveBeenCalledWith('vault-1', 'test-token')
    expect(wrapper.text()).toContain('Your Listings')
  })
})
