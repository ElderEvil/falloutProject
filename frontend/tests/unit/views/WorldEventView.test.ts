import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createIconifyMock } from '../helpers/mocks'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, disposePinia, getActivePinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import WorldEventView from '@/modules/world-event/views/WorldEventView.vue'
import { useWorldEventStore, type WorldEvent } from '@/modules/world-event/stores/worldEvent'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'

// Iconify is mocked so icon assertions read the resolved name from `data-icon`.
vi.mock('@iconify/vue', () => createIconifyMock({ template: '<svg :data-icon="icon"></svg>' }))

function eventFixture(overrides: Partial<WorldEvent> = {}): WorldEvent {
  return {
    event_id: 'evt-1',
    kind: 'community',
    title: 'Radstorm Surge',
    description: 'Every vault vents its purifiers at once.',
    target_amount: 5000,
    progress_amount: 2500,
    participant_count: 12,
    contribution: 750,
    personal_min: 1000,
    can_claim: true,
    status: 'ACTIVE',
    starts_at: '2026-01-01T00:00:00Z',
    ends_at: new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString(),
    extended_at: null,
    reward: [{ reward_type: 'caps', amount: 250 }],
    ...overrides,
  }
}

describe('WorldEventView', () => {
  let router: Router
  let wrapper: VueWrapper | undefined
  let store: ReturnType<typeof useWorldEventStore>

  beforeEach(async () => {
    setActivePinia(createPinia())
    store = useWorldEventStore()
    // The view loads on mount and polls; keep both off the network.
    vi.spyOn(store, 'load').mockResolvedValue()

    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id/world-event', component: WorldEventView }],
    })
    await router.push('/vault/vault-1/world-event')
    await router.isReady()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    const pinia = getActivePinia()
    if (pinia) disposePinia(pinia)
  })

  async function mountView() {
    wrapper = mount(WorldEventView, {
      global: {
        plugins: [router],
        stubs: {
          VaultPageShell: { template: '<main><slot /></main>' },
          PageContentRail: { template: '<div><slot /></div>' },
          PageHeader: {
            props: ['title'],
            template: '<header><h1>{{ title }}</h1></header>',
          },
          TerminalLoadingState: true,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  function iconsInMetrics(): string[] {
    return wrapper!
      .get('.event-metrics')
      .findAll('svg')
      .map((icon) => icon.attributes('data-icon') ?? '')
  }

  const statusMetric = () =>
    wrapper!.findAllComponents(TerminalMetric).find((metric) => metric.props('label') === 'STATUS')

  it('renders the title, status chip and four metric tiles', async () => {
    store.event = eventFixture()
    await mountView()

    expect(wrapper!.get('h2').text()).toBe('Radstorm Surge')
    expect(wrapper!.get('.status-chip').text()).toContain('ACTIVE')

    const metrics = wrapper!.get('.event-metrics')
    expect(metrics.text()).toContain('YOUR CONTRIBUTION')
    expect(metrics.text()).toContain('750 / 1000')
    expect(metrics.text()).toContain('VAULTS')
    expect(metrics.text()).toContain('12')
    expect(metrics.text()).toContain('STATUS')
    expect(metrics.text()).toContain('ENDS')
    expect(metrics.text()).toMatch(/left|No deadline|Ended/)

    // At least one icon in the metrics strip, and the ACTIVE status icon.
    expect(iconsInMetrics().length).toBeGreaterThan(0)
    expect(iconsInMetrics()).toContain('mdi:access-point')
    expect(statusMetric()?.props('tone')).toBe('primary')
  })

  it('shows the reward line as "<amount> <type>"', async () => {
    store.event = eventFixture()
    await mountView()

    const reward = wrapper!.get('.reward-line')
    expect(reward.text()).toContain('250 caps')
    expect(reward.get('svg').attributes('data-icon')).toBe('mdi:coins')
  })

  it('joins multiple rewards and lowercases the reward type', async () => {
    store.event = eventFixture({
      reward: [
        { reward_type: 'CAPS', amount: 250 },
        { reward_type: 'Lunchbox', amount: 1 },
      ],
    })
    await mountView()

    expect(wrapper!.get('.reward-line').text()).toContain('250 caps + 1 lunchbox')
  })

  it('omits the reward line when the event has no rewards', async () => {
    store.event = eventFixture({ reward: [] })
    await mountView()

    expect(wrapper!.find('.reward-line').exists()).toBe(false)
  })

  it('renders the EXPIRED status with its icon and label', async () => {
    store.event = eventFixture({ status: 'EXPIRED', can_claim: false, ends_at: null })
    await mountView()

    expect(wrapper!.get('.status-chip').text()).toContain('EXPIRED')
    expect(iconsInMetrics()).toContain('mdi:close-octagon-outline')
    expect(statusMetric()?.props('tone')).toBe('danger')
  })

  it('disables the claim button and explains the qualification rule', async () => {
    store.event = eventFixture({ can_claim: false })
    await mountView()

    const button = wrapper!.get('button')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper!.text()).toContain('Contribute 1000 to qualify.')
  })

  it('renders the empty state when the relay has no event', async () => {
    store.event = null
    await mountView()

    expect(wrapper!.text()).toContain('No world event is broadcasting right now.')
    expect(wrapper!.find('.event-metrics').exists()).toBe(false)
  })
})
