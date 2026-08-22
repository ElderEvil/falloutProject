import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import OverseerBriefing from '@/modules/vault/components/shell/OverseerBriefing.vue'

const defaultProps = {
  vaultNumber: 42,
  activeIncidentCount: 0,
  activeExplorationCount: 2,
  trainingCount: 1,
  questingCount: 0,
  unassignedCount: 0,
  populationUtilization: 64,
  happiness: 82,
  resourceWarnings: [],
  dwellersPath: '/vault/vault-1/dwellers',
}

describe('OverseerBriefing', () => {
  it('summarizes a stable vault and active operations', () => {
    const wrapper = mount(OverseerBriefing, { props: defaultProps })

    expect(wrapper.text()).toContain('VAULT STATUS')
    expect(wrapper.text()).toContain('VAULT 42')
    expect(wrapper.text()).toContain('3 active operations')
    expect(wrapper.text()).toContain('SYSTEMS NOMINAL')
    expect(wrapper.findAll('.briefing-metric')).toHaveLength(6)
    expect(wrapper.text()).toContain('EXPEDITIONS')
    expect(wrapper.text()).toContain('TRAINING')
    expect(wrapper.text()).toContain('QUESTS')
    expect(wrapper.text()).toContain('UNASSIGNED')
    expect(wrapper.text()).toContain('64%')
    expect(wrapper.text()).toContain('82%')
    expect(wrapper.classes()).not.toContain('bg-surface-warm')
  })

  it('prioritizes incidents and emits a response action', async () => {
    const wrapper = mount(OverseerBriefing, {
      props: {
        ...defaultProps,
        activeIncidentCount: 2,
        resourceWarnings: [{ type: 'critical_water', message: 'Water reserves are critical' }],
      },
    })

    expect(wrapper.text()).toContain('2 INCIDENTS REQUIRE RESPONSE')
    expect(wrapper.text()).toContain('Water reserves are critical')

    await wrapper.get('.briefing-respond button').trigger('click')

    expect(wrapper.emitted('reviewIncidents')).toHaveLength(1)
  })

  it('links unassigned dwellers to the dweller roster', () => {
    const wrapper = mount(OverseerBriefing, {
      props: { ...defaultProps, unassignedCount: 3 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })

    expect(wrapper.text()).toContain('3 DWELLERS AWAIT ASSIGNMENT')
    expect(wrapper.find('a').exists()).toBe(true)
  })
})
