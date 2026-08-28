import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { UProgressBar } from '@/core/components/ui'
import ExplorerCard from '@/modules/exploration/components/ExplorerCard.vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { Dweller } from '@/modules/dwellers/models/dweller'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'vault-1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@iconify/vue', () => ({
  Icon: { name: 'Icon', template: '<span class="icon-mock" />' },
}))

const exploration = {
  id: 'exploration-1',
  vault_id: 'vault-1',
  dweller_id: 'dweller-1',
  status: 'active',
  duration: 8,
  start_time: '2026-01-01T00:00:00Z',
  end_time: null,
  events: [],
  loot_collected: [],
  total_distance: 0,
  total_caps_found: 0,
  enemies_encountered: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  dweller_strength: 1,
  dweller_perception: 1,
  dweller_endurance: 1,
  dweller_charisma: 1,
  dweller_intelligence: 1,
  dweller_agility: 1,
  dweller_luck: 1,
  stimpaks: 0,
  radaways: 0,
} as Exploration

const dweller = {
  first_name: 'Lucy',
  last_name: 'MacLean',
  image_url: 'example.com/lucy.png',
  thumbnail_url: 'example.com/lucy-thumb.png',
} as Dweller

describe('ExplorerCard', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the exploring dweller portrait', () => {
    const wrapper = mount(ExplorerCard, { props: { exploration, dweller } })

    expect(wrapper.find('.dweller-portrait').attributes('src')).toBe('http://example.com/lucy-thumb.png')
    expect(wrapper.find('.dweller-portrait').attributes('alt')).toBe('Lucy MacLean portrait')

    wrapper.unmount()
  })

  it('uses the thumbnail when image_url is blank', () => {
    const wrapper = mount(ExplorerCard, {
      props: { exploration, dweller: { ...dweller, image_url: '', thumbnail_url: 'example.com/thumb.png' } },
    })

    expect(wrapper.find('.dweller-portrait').attributes('src')).toBe('http://example.com/thumb.png')
  })

  it('keeps long equipment names within their exploration-card slots', () => {
    const wrapper = mount(ExplorerCard, {
      props: {
        exploration,
        dweller: {
          ...dweller,
          weapon: { name: 'Experimental Plasma Rifle With an Extremely Long Name' },
        },
      },
    })

    expect(wrapper.find('.equipment-slot').classes()).toContain('min-w-0')
    expect(wrapper.find('.equip-name').text()).toContain('Experimental Plasma Rifle')
  })

  it('updates progress and remaining time while mounted, then stops its clock when unmounted', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T01:00:00Z'))
    const wrapper = mount(ExplorerCard, { props: { exploration, dweller } })

    expect(wrapper.findComponent(UProgressBar).props('modelValue')).toBeGreaterThan(0)
    expect(wrapper.find('.progress-percentage').text()).toBe('13%')
    expect(wrapper.find('.progress-time').text()).toBe('7h 0m remaining')
    expect(vi.getTimerCount()).toBe(1)

    await vi.advanceTimersByTimeAsync(60 * 60 * 1000)
    await nextTick()

    expect(wrapper.find('.progress-percentage').text()).toBe('25%')
    expect(wrapper.find('.progress-time').text()).toBe('6h 0m remaining')

    wrapper.unmount()

    expect(vi.getTimerCount()).toBe(0)
  })

  it('preserves timezone offsets in exploration start times', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T05:00:00Z'))
    const wrapper = mount(ExplorerCard, {
      props: {
        exploration: { ...exploration, start_time: '2026-01-01T00:00:00-05:00' },
        dweller,
      },
    })

    expect(wrapper.find('.progress-percentage').text()).toBe('0%')

    wrapper.unmount()
  })
})
