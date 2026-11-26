import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import DeadDwellerCard from '@/modules/dwellers/components/death/DeadDwellerCard.vue'
import type { DwellerDead } from '@/modules/dwellers/models/dweller'

const revivableDweller: DwellerDead = {
  id: 'dweller-1',
  first_name: 'Cass',
  last_name: 'Vance',
  level: 5,
  thumbnail_url: null,
  death_timestamp: '2026-10-16T00:00:00',
  death_cause: 'incident',
  is_permanently_dead: false,
  epitaph: null,
  days_until_permanent: 5,
}

const stubs = {
  Card: { template: '<div><slot /></div>' },
  Button: { template: '<button><slot /></button>' },
  Badge: { template: '<span><slot /></span>' },
  Icon: { template: '<span />' },
}

describe('DeadDwellerCard revival controls', () => {
  it.each([
    ['a revivable death (standard vault)', {}, 'REVIVE', 'PERMANENTLY DEAD'],
    [
      'a permanent death (survival vault)',
      { is_permanently_dead: true, days_until_permanent: null },
      'PERMANENTLY DEAD',
      'REVIVE',
    ],
  ] as const)('offers the right control for %s', (_name, patch, shown, hidden) => {
    const wrapper = mount(DeadDwellerCard, {
      props: { dweller: { ...revivableDweller, ...patch } },
      global: { stubs },
    })

    expect(wrapper.text()).toContain(shown)
    expect(wrapper.text()).not.toContain(hidden)
  })
})
