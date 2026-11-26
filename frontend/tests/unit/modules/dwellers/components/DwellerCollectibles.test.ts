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

  it('shows a cleared magazine boon as removed rather than a zero bonus', async () => {
    vi.mocked(getDwellerCollectibles).mockResolvedValue([
      {
        ...found,
        key: 'guns_and_bullets',
        name: 'Guns and Bullets',
        stat: 'perception',
        amount: 0,
      },
    ])

    const wrapper = mountCollectibles()
    await flushPromises()

    expect(wrapper.text()).toContain('Guns and Bullets')
    expect(wrapper.text()).toContain('BONUS REMOVED · PERCEPTION')
    expect(wrapper.text()).not.toContain('PERMANENT +0')
  })

  it.each([
    ['the dweller has found nothing', [] as unknown[], 'No collectibles yet'],
    ['the read fails', new Error('network down'), 'network down'],
  ] as const)('surfaces %s instead of a collection', async (_name, result, text) => {
    if (result instanceof Error) {
      vi.mocked(getDwellerCollectibles).mockRejectedValue(result)
    } else {
      vi.mocked(getDwellerCollectibles).mockResolvedValue(result as never)
    }

    const wrapper = mountCollectibles()
    await flushPromises()

    expect(wrapper.text()).toContain(text)
    // An error must never be presented as a legitimately empty collection.
    expect(wrapper.text().includes('No collectibles yet')).toBe(text === 'No collectibles yet')
    expect(wrapper.find('img').exists()).toBe(false)
  })
})
