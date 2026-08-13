import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
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
  image_url: 'https://example.com/lucy.png',
} as Dweller

describe('ExplorerCard', () => {
  it('shows the exploring dweller portrait', () => {
    const wrapper = mount(ExplorerCard, { props: { exploration, dweller } })

    expect(wrapper.find('.dweller-portrait').attributes('src')).toBe('https://example.com/lucy.png')
    expect(wrapper.find('.dweller-portrait').attributes('alt')).toBe('Lucy MacLean portrait')
  })
})
