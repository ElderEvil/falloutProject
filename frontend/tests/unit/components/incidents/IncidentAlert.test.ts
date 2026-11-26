import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import IncidentAlert from '@/modules/combat/components/incidents/IncidentAlert.vue'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { IncidentType, IncidentStatus } from '@/modules/combat/models/incident'
import type { Incident, IncidentTeamMember } from '@/modules/combat/models/incident'

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<div class="mock-icon" :data-icon="icon"></div>' })
)

const mockIncident: Incident = {
  id: 'incident-1',
  vault_id: 'vault-1',
  room_id: 'room-1',
  room_name: 'Power Generator',
  type: IncidentType.RAIDER_ATTACK,
  status: IncidentStatus.ACTIVE,
  difficulty: 5,
  start_time: '2025-01-01T00:00:00Z',
  damage_dealt: 10,
  enemies_defeated: 2,
  spread_count: 0,
  rooms_affected: ['room-1'],
  last_spread_time: null,
  loot: null,
  resolved_at: null,
  duration: 60,
}

const teamMember: IncidentTeamMember = {
  id: 'tm-1',
  team_id: 'team-1',
  dweller_id: 'dweller-1',
  slot_number: 1,
  status: 'assigned',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const render = (incidents: Incident[] = [mockIncident]) =>
  mount(IncidentAlert, { props: { incidents } })

const stars = (incidents: Incident[] = [mockIncident]) => render(incidents).text().match(/★/g)

describe('IncidentAlert', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-01-01T00:01:00Z')) // 1 minute after start
  })

  it('renders the live incident with its type, elapsed time and label', () => {
    const wrapper = render()

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('RAIDER ATTACK')
    expect(wrapper.text()).toMatch(/\d+:\d+/)
    expect(wrapper.get('button').attributes('aria-label')).toBe('Open RAIDER ATTACK incident')
  })

  it('handles an empty incidents array', () => {
    expect(render([]).exists()).toBe(true)
  })

  it.each([
    [5, 5],
    [10, 10],
    [1, 1],
  ])('draws one star per difficulty point (%i)', (difficulty, expected) => {
    expect(stars([{ ...mockIncident, difficulty }])).toHaveLength(expected)
  })

  it.each([
    [IncidentType.RAIDER_ATTACK, 'mdi:robber'],
    [IncidentType.FIRE, 'mdi:fire'],
    [IncidentType.RADSCORPION_ATTACK, 'mdi:spider'],
    [IncidentType.RADROACH_INFESTATION, 'mdi:bug'],
    [IncidentType.MOLE_RAT_ATTACK, 'mdi:paw'],
    [IncidentType.DEATHCLAW_ATTACK, 'mdi:axe-battle'],
    [IncidentType.FERAL_GHOUL_ATTACK, 'mdi:biohazard'],
  ])('maps %s onto its icon', (type, icon) => {
    expect(
      render([{ ...mockIncident, type }])
        .find('.mock-icon')
        .attributes('data-icon')
    ).toBe(icon)
  })

  it('shows a count badge and only the primary incident when several are live', () => {
    const wrapper = render([
      mockIncident,
      { ...mockIncident, id: 'incident-2', type: IncidentType.FIRE },
      { ...mockIncident, id: 'incident-3', type: IncidentType.RADROACH_INFESTATION },
    ])

    expect(wrapper.text()).toContain('3 ACTIVE')
    expect(wrapper.text()).toContain('RAIDER ATTACK')
    expect(wrapper.text()).not.toContain('FIRE')
  })

  it('should emit click event with incident id', async () => {
    const wrapper = render()

    await wrapper.trigger('click')

    expect(wrapper.emitted('click')).toHaveLength(1)
    expect(wrapper.emitted('click')?.[0]).toEqual(['incident-1'])
  })

  it.each([
    [[mockIncident], true],
    [[], false],
  ])('marks a live incident with the sanctioned live-status tier (%#)', (incidents, live) => {
    expect(
      render(incidents as Incident[])
        .find('.incident-alert')
        .classes()
        .includes('badge-live')
    ).toBe(live)
  })

  describe('Responder status', () => {
    it('shows the responder count on the informational badge tier', () => {
      useIncidentStore().incidentTeams.set('incident-1', [teamMember])

      const wrapper = render()
      const chip = wrapper.find('.badge-info')

      expect(wrapper.text()).toContain('1 on scene')
      expect(chip.exists()).toBe(true)
      expect(chip.classes()).not.toContain('badge-live')
      expect(chip.classes()).not.toContain('badge-action')
    })

    it('shows "No responders" when the primary team is loaded but empty', () => {
      useIncidentStore().incidentTeams.set('incident-1', [])

      expect(render().text()).toContain('No responders')
    })

    it('shows nothing while the primary team has not loaded', () => {
      const text = render().text()

      expect(text).not.toContain('on scene')
      expect(text).not.toContain('No responders')
    })
  })
})
