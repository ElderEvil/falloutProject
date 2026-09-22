import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import TradingPostPanel from '@/modules/trading/components/TradingPostPanel.vue'
import { tradingService } from '@/modules/trading/services/tradingService'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { TradeMarketResponse, TradeOffer, TradeResultResponse } from '@/modules/trading/models/trading'

const mockToast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }

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

const dweller = (overrides: Partial<DwellerShort> = {}): DwellerShort =>
  ({
    id: 'dweller-1',
    first_name: 'Nora',
    last_name: 'Vance',
    level: 5,
    age_group: 'adult',
    gender: 'female',
    rarity: 'common',
    ...overrides,
  }) as DwellerShort

const offer = (overrides: Partial<TradeOffer> = {}): TradeOffer => ({
  dweller: dweller(),
  price: 100,
  has_bio: true,
  places_visited: 3,
  ...overrides,
})

const market = (overrides: Partial<TradeMarketResponse> = {}): TradeMarketResponse => ({
  market_offers: [],
  my_listings: [],
  bottle_caps: 500,
  ...overrides,
})

const result = (overrides: Partial<TradeResultResponse> = {}): TradeResultResponse => ({
  dweller_id: 'dweller-1',
  price: 100,
  bottle_caps: 600,
  ...overrides,
})

const findButton = (wrapper: ReturnType<typeof mountWithSetup>, label: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(label))!

const mountPanel = (vaultId = 'vault-1') =>
  mountWithSetup(TradingPostPanel, { props: { vaultId } })

describe('TradingPostPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // The auth store is localStorage-backed; the fresh Pinia created by
    // mountWithSetup reads the token from here at store creation.
    localStorage.setItem('token', 'test-token')
    vi.mocked(tradingService.getMarket).mockResolvedValue(market())
  })

  it('loads the market on mount and populates both lists', async () => {
    vi.mocked(tradingService.getMarket).mockResolvedValue(
      market({
        my_listings: [offer({ dweller: dweller({ id: 'd1', first_name: 'Nora' }) })],
        market_offers: [offer({ dweller: dweller({ id: 'd2', first_name: 'Cait' }), price: 250 })],
        bottle_caps: 500,
      })
    )
    const wrapper = mountPanel()
    await flushPromises()

    expect(tradingService.getMarket).toHaveBeenCalledWith('vault-1', 'test-token')
    expect(wrapper.text()).toContain('500 caps')
    expect(wrapper.text()).toContain('Nora')
    expect(wrapper.text()).toContain('Cait')
    expect(wrapper.text()).toContain('250 caps')
  })

  it('shows empty-state hints when there is nothing to trade', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('Soft-delete a dweller to list them here.')
    expect(wrapper.text()).toContain('No dwellers on the market right now.')
  })

  it('sells a listed dweller and refreshes the market', async () => {
    vi.mocked(tradingService.getMarket).mockResolvedValue(market({ my_listings: [offer()] }))
    vi.mocked(tradingService.sellDweller).mockResolvedValue(result())
    const wrapper = mountPanel()
    await flushPromises()

    await findButton(wrapper, 'Sell').trigger('click')
    await flushPromises()

    expect(tradingService.sellDweller).toHaveBeenCalledWith('vault-1', 'dweller-1', 'test-token')
    expect(mockToast.success).toHaveBeenCalledWith('Sold for 100 caps!')
    expect(tradingService.getMarket).toHaveBeenCalledTimes(2)
  })

  it('buys a market dweller and reports the price', async () => {
    vi.mocked(tradingService.getMarket).mockResolvedValue(market({ market_offers: [offer()] }))
    vi.mocked(tradingService.buyDweller).mockResolvedValue(result({ bottle_caps: 400 }))
    const wrapper = mountPanel()
    await flushPromises()

    await findButton(wrapper, 'Buy').trigger('click')
    await flushPromises()

    expect(tradingService.buyDweller).toHaveBeenCalledWith('vault-1', 'dweller-1', 'test-token')
    expect(mockToast.success).toHaveBeenCalledWith('Nora joined the vault for 100 caps!')
    expect(tradingService.getMarket).toHaveBeenCalledTimes(2)
  })

  it('disables buying when the offer exceeds the vault caps', async () => {
    vi.mocked(tradingService.getMarket).mockResolvedValue(
      market({ market_offers: [offer({ price: 900 })], bottle_caps: 500 })
    )
    const wrapper = mountPanel()
    await flushPromises()

    expect(findButton(wrapper, 'Buy').attributes('disabled')).toBeDefined()
  })

  it('disables the in-flight action while a trade is pending and re-enables it after', async () => {
    let resolveSell!: (value: TradeResultResponse) => void
    vi.mocked(tradingService.sellDweller).mockReturnValue(
      new Promise((resolve) => {
        resolveSell = resolve
      })
    )
    vi.mocked(tradingService.getMarket).mockResolvedValue(
      market({
        my_listings: [offer()],
        market_offers: [offer({ dweller: dweller({ id: 'dweller-2' }) })],
      })
    )
    const wrapper = mountPanel()
    await flushPromises()

    const sellButton = findButton(wrapper, 'Sell')
    await sellButton.trigger('click')
    await flushPromises()

    // Only the busy offer's action is disabled; the other dweller's stays live.
    expect(sellButton.attributes('disabled')).toBeDefined()
    expect(findButton(wrapper, 'Buy').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-icon="mdi:loading"]').exists()).toBe(true)

    resolveSell(result())
    await flushPromises()

    // The refresh re-renders the lists, so re-query the fresh button.
    expect(findButton(wrapper, 'Sell').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-icon="mdi:loading"]').exists()).toBe(false)
  })

  it('reports a market load failure through the toast', async () => {
    vi.mocked(tradingService.getMarket).mockRejectedValue(new Error('boom'))
    const wrapper = mountPanel()
    await flushPromises()

    expect(mockToast.error).toHaveBeenCalledWith('boom')
  })

  it('refetches the market when the vault changes', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()

    expect(tradingService.getMarket).toHaveBeenCalledTimes(2)
    expect(tradingService.getMarket).toHaveBeenLastCalledWith('vault-2', 'test-token')
  })
})
