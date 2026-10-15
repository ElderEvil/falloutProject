import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import VaultOperationsCard from '@/modules/profile/components/VaultOperationsCard.vue'

const activeRecord = {
  total_dwellers_created: 12,
  total_caps_earned: 5_000,
  total_explorations: 8,
  total_rooms_built: 4,
  total_incidents: 9,
  total_incidents_won: 6,
  total_incidents_lost: 3,
}

describe('VaultOperationsCard', () => {
  it('presents all lifetime operation records', () => {
    const wrapper = mount(VaultOperationsCard, { props: { record: activeRecord } })

    expect(wrapper.get('[aria-label="Vault operations"]').text()).toContain('Vault operations')
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('5,000')
    expect(wrapper.text()).toContain('8')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Population')
    expect(wrapper.text()).toContain('Incidents')
    expect(wrapper.text()).toContain('Incidents won')
    expect(wrapper.text()).toContain('Incidents lost')
    expect(wrapper.text()).toContain('9')
  })

  it('explains why an empty operation record has no values yet', () => {
    const wrapper = mount(VaultOperationsCard, {
      props: {
        record: {
          total_dwellers_created: 0,
          total_caps_earned: 0,
          total_explorations: 0,
          total_rooms_built: 0,
          total_incidents: 0,
          total_incidents_won: 0,
          total_incidents_lost: 0,
        },
      },
    })

    expect(wrapper.text()).toContain('No vault activity reported yet.')
    expect(wrapper.text()).toContain('Records accumulate as your vault operates.')
  })

  it('announces when the live record is refreshing', () => {
    const wrapper = mount(VaultOperationsCard, { props: { record: activeRecord, refreshing: true } })

    expect(wrapper.get('[role="status"]').text()).toContain('Refreshing')
  })
})
