import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouterMock } from '../../../helpers/mocks'
import WorldEventBanner from '@/modules/world-event/components/WorldEventBanner.vue'
import { worldEventService } from '@/modules/world-event/services/worldEventService'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))
vi.mock('@/modules/world-event/services/worldEventService', () => ({
  worldEventService: { getEvent: vi.fn(), claim: vi.fn() },
}))

const event = {
  event_id: 'event-1',
  title: 'Wasteland Relay',
  target_amount: 100,
  progress_amount: 40,
  contribution: 5,
  personal_min: 5,
  can_claim: false,
}

/** Mount the banner with the world-event flag resolved, then let it read. */
const loadBanner = async (worldEvents: boolean) => {
  const flags = useFeatureFlagsStore()
  flags.loaded = true
  flags.worldEvents = worldEvents
  const wrapper = mount(WorldEventBanner, {
    props: { vaultId: 'vault-1' },
    global: {
      stubs: { RouterLink: { template: '<a class="event-link"><slot /></a>' } },
    },
  })
  await flushPromises()
  return wrapper
}

describe('WorldEventBanner', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('does not ask the API for an event while the feature ships dark', async () => {
    // The endpoint 404s when the flag is off; asking anyway logged a failed request per vault load.
    const wrapper = await loadBanner(false)

    expect(worldEventService.getEvent).not.toHaveBeenCalled()
    expect(wrapper.find('.event-link').exists()).toBe(false)
  })

  it('loads and shows the event when the feature is enabled', async () => {
    vi.mocked(worldEventService.getEvent).mockResolvedValue(event)

    const wrapper = await loadBanner(true)

    expect(worldEventService.getEvent).toHaveBeenCalledWith('vault-1')
    expect(wrapper.find('.event-link').text()).toContain('Wasteland Relay')
    expect(wrapper.find('.event-link').text()).toContain('40 / 100')
  })
})
