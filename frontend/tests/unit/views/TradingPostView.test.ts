import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { mountWithSetup } from '../helpers/mountWithSetup'
import TradingPostView from '@/modules/trading/views/TradingPostView.vue'
import { tradingService } from '@/modules/trading/services/tradingService'
import type { TradeMarketResponse } from '@/modules/trading/models/trading'

const mockToast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'vault-1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

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

// Keyboard roving focus needs the component inside the live document, so the
// view is mounted with attachTo and torn down between tests.
let wrapper: VueWrapper | null = null

const mountView = () => {
  wrapper = mountWithSetup(TradingPostView, {
    attachTo: document.body,
    global: { stubs: { SidePanel: true } },
  })
  return wrapper
}

// Inactive TabsContent stays in the DOM with a `hidden` attribute (its slot is
// unmounted), so the visible panel is the one without `hidden`.
const visiblePanel = (w: VueWrapper) =>
  w.findAll('[role="tabpanel"]').find((panel) => panel.attributes('hidden') === undefined)!

describe('TradingPostView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    vi.mocked(tradingService.getMarket).mockResolvedValue(market())
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('renders a tablist with Dwellers active by default', async () => {
    const wrapper = mountView()
    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(3)
    expect(tabs.map((tab) => tab.text())).toEqual(['Dwellers', 'Weapons', 'Outfits'])
    expect(tabs[0].attributes('aria-selected')).toBe('true')
    expect(tabs[1].attributes('aria-selected')).toBe('false')
    expect(tabs[2].attributes('aria-selected')).toBe('false')

    // The dwellers panel is the only visible content.
    expect(visiblePanel(wrapper).exists()).toBe(true)
    expect(wrapper.text()).toContain('Your Listings')
    expect(wrapper.text()).not.toContain('Weapon trading coming soon')
    expect(wrapper.text()).not.toContain('Outfit trading coming soon')
  })

  it('switches content when a tab is activated and wires the tabpanel to its trigger', async () => {
    const wrapper = mountView()
    await flushPromises()

    // reka-ui activates tabs on mousedown (not click).
    await wrapper.findAll('[role="tab"]')[1].trigger('mousedown')
    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs[1].attributes('aria-selected')).toBe('true')
    expect(tabs[0].attributes('aria-selected')).toBe('false')

    const panel = visiblePanel(wrapper)
    expect(panel.attributes('aria-labelledby')).toBe(tabs[1].attributes('id'))
    expect(wrapper.text()).toContain('Weapon trading coming soon')
    expect(wrapper.text()).not.toContain('Your Listings')
  })

  it('moves focus and activates the next tab with ArrowRight', async () => {
    const wrapper = mountView()
    await flushPromises()

    // Tab into the tablist first: roving focus assigns the tab stop on focus.
    wrapper.findAll('[role="tab"]')[0].element.focus()
    await flushPromises()
    expect(document.activeElement?.textContent).toBe('Dwellers')

    await wrapper.findAll('[role="tab"]')[0].trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs[1].attributes('aria-selected')).toBe('true')
    expect(wrapper.text()).toContain('Weapon trading coming soon')
  })

  it('remounts the dwellers panel on tab return, refetching the market', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(tradingService.getMarket).toHaveBeenCalledTimes(1)

    await wrapper.findAll('[role="tab"]')[1].trigger('mousedown')
    await flushPromises()
    await wrapper.findAll('[role="tab"]')[0].trigger('mousedown')
    await flushPromises()

    expect(tradingService.getMarket).toHaveBeenCalledTimes(2)
    expect(tradingService.getMarket).toHaveBeenLastCalledWith('vault-1', 'test-token')
  })
})
