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
  it('offers REVIVE for a revivable death (standard vault)', () => {
    const wrapper = mount(DeadDwellerCard, {
      props: { dweller: revivableDweller },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('REVIVE')
  })

  it('shows no REVIVE affordance for a permanent death (survival vault)', () => {
    const wrapper = mount(DeadDwellerCard, {
      props: {
        dweller: { ...revivableDweller, is_permanently_dead: true, days_until_permanent: null },
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('PERMANENTLY DEAD')
    expect(wrapper.text()).not.toContain('REVIVE')
  })
})
