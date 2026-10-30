import { describe, expect, it } from 'vite-plus/test'
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
  readyActions: [],
}

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="typeof to === \'string\' ? to : to.path"><slot /></a>',
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

  it('renders ready actions with labels, counts, and routes', () => {
    const wrapper = mount(OverseerBriefing, {
      props: {
        ...defaultProps,
        readyActions: [
          {
            kind: 'quest_claim' as const,
            label: 'Quest rewards ready',
            route: '/vault/vault-1?claimQuest=quest-1',
            count: 2,
          },
          {
            kind: 'crafting_collect' as const,
            label: 'Crafted items ready',
            route: '/vault/vault-1?collectCraft=1',
            count: 1,
          },
        ],
      },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })

    const readyActions = wrapper.get('[data-testid="ready-actions"]')
    expect(readyActions.text()).toContain('READY ACTIONS')
    expect(readyActions.text()).toContain('Quest rewards ready')
    expect(readyActions.text()).toContain('2')
    expect(readyActions.text()).toContain('Crafted items ready')

    const questLink = wrapper.get('[data-testid="ready-action-quest_claim"]')
    expect(questLink.attributes('href')).toContain('?claimQuest=')
    expect(wrapper.get('[data-testid="ready-action-crafting_collect"]').exists()).toBe(true)
  })

  it('renders attention rows before ready actions', () => {
    const wrapper = mount(OverseerBriefing, {
      props: {
        ...defaultProps,
        activeIncidentCount: 1,
        readyActions: [
          {
            kind: 'quest_claim' as const,
            label: 'Quest rewards ready',
            route: '/vault/vault-1?claimQuest=quest-1',
            count: 1,
          },
        ],
      },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })

    const html = wrapper.element.innerHTML
    expect(html.indexOf('1 INCIDENT REQUIRES RESPONSE')).toBeGreaterThanOrEqual(0)
    expect(html.indexOf('1 INCIDENT REQUIRES RESPONSE')).toBeLessThan(html.indexOf('READY ACTIONS'))
  })

  it('caps attention rows at three and expands on demand', async () => {
    const wrapper = mount(OverseerBriefing, {
      props: {
        ...defaultProps,
        activeIncidentCount: 1,
        resourceWarnings: [
          { type: 'critical_water', message: 'Water reserves are critical' },
          { type: 'low_food', message: 'Food reserves are low' },
        ],
        unassignedCount: 4,
      },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })

    expect(wrapper.text()).toContain('1 INCIDENT REQUIRES RESPONSE')
    expect(wrapper.text()).not.toContain('4 DWELLERS AWAIT ASSIGNMENT')

    const toggle = wrapper.get('[data-testid="attention-overflow-toggle"]')
    expect(toggle.text()).toBe('VIEW ALL (4)')

    await toggle.trigger('click')

    expect(wrapper.text()).toContain('4 DWELLERS AWAIT ASSIGNMENT')
    expect(wrapper.get('[data-testid="attention-overflow-toggle"]').text()).toBe('SHOW LESS')
  })
})
