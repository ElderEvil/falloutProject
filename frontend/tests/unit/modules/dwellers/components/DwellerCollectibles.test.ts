import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import DwellerCollectibles from '@/modules/dwellers/components/DwellerCollectibles.vue'
import { getDwellerCollectibles } from '@/modules/dwellers/api/collectibles'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../../helpers/dwellerDetailContext'
import type { Dweller } from '@/modules/dwellers/models/dweller'

enableAutoUnmount(afterEach)

vi.mock('@/modules/dwellers/api/collectibles', () => ({ getDwellerCollectibles: vi.fn() }))
vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token', sessionGeneration: 0 }),
}))

const found = {
  key: 'strength',
  name: 'Strength Bobblehead',
  stat: 'strength',
  amount: 1,
  image: 'bobblehead_images/strength.png',
  location: 'Poseidon Energy',
  found_at: '2026-11-21T00:00:00Z',
}

function mountCollectibles() {
  const context = createMockDwellerDetailContext({
    dweller: ref({ id: 'dweller-1' } as unknown as Dweller),
  })
  return mountWithDwellerContext(DwellerCollectibles, { context })
}

describe('DwellerCollectibles', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the found bobblehead with its permanent bonus', async () => {
    vi.mocked(getDwellerCollectibles).mockResolvedValue([found])

    const wrapper = mountCollectibles()
    await flushPromises()

    expect(wrapper.text()).toContain('Strength Bobblehead')
    expect(wrapper.text()).toContain('PERMANENT +1 STRENGTH')
    expect(wrapper.text()).toContain('Poseidon Energy')
    expect(wrapper.find('img').attributes('src')).toContain('bobblehead_images/strength.png')
  })

  it('shows the empty state when the dweller has found nothing', async () => {
    vi.mocked(getDwellerCollectibles).mockResolvedValue([])

    const wrapper = mountCollectibles()
    await flushPromises()

    expect(wrapper.text()).toContain('No bobbleheads yet')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('surfaces a failed read instead of an empty collection', async () => {
    vi.mocked(getDwellerCollectibles).mockRejectedValue(new Error('network down'))

    const wrapper = mountCollectibles()
    await flushPromises()

    expect(wrapper.text()).toContain('network down')
    expect(wrapper.text()).not.toContain('No bobbleheads yet')
  })
})
