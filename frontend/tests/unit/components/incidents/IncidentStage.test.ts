import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import IncidentStage from '@/modules/combat/components/incidents/IncidentStage.vue'
import { IncidentStatus, IncidentType, type Incident } from '@/modules/combat/models/incident'

vi.mock('@iconify/vue', () => ({
  Icon: { props: ['icon'], template: '<span :data-icon="icon" />' },
}))

const baseIncident: Incident = {
  id: 'incident-1',
  vault_id: 'vault-1',
  room_id: 'room-1',
  room_name: 'Power Generator',
  type: IncidentType.RAIDER_ATTACK,
  status: IncidentStatus.ACTIVE,
  difficulty: 4,
  start_time: '2026-09-05T00:00:00Z',
  end_time: null,
  duration: 60,
  elapsed_time: 10,
  damage_dealt: 5,
  enemies_defeated: 1,
  loot: null,
  rooms_affected: ['room-1'],
  spread_count: 0,
  created_at: '2026-09-05T00:00:00Z',
  updated_at: '2026-09-05T00:00:00Z',
  family: 'intrusion',
  objective: 'defeat',
  progress: { current: 1, target: 3, label: 'Threat neutralized' },
  risk: { kind: 'Physical threat', rooms_affected: 1 },
  response: { label: 'Send defenders' },
  events: [
    {
      id: 'event-1',
      kind: 'round',
      message: 'Responders exchanged fire.',
      data: { damage_to_dwellers: 4, damage_to_threat: 7 },
    },
  ],
}

const dwellers = [
  { id: 'dweller-1', first_name: 'Nora', room_id: 'room-1', health: 80, max_health: 100 },
] as never

describe('IncidentStage', () => {
  it('renders opposing combatants and damage over their sides', () => {
    const wrapper = mount(IncidentStage, { props: { incident: baseIncident, dwellers } })

    expect(wrapper.text()).toContain('RESPONDERS')
    expect(wrapper.text()).toContain('THREAT')
    expect(wrapper.text()).toContain('2 remaining')
    expect(wrapper.text()).toContain('-4')
    expect(wrapper.text()).toContain('-7')
  })

  it('renders a containment state instead of enemy combatants for hazards', () => {
    const wrapper = mount(IncidentStage, {
      props: {
        incident: {
          ...baseIncident,
          type: IncidentType.FIRE,
          family: 'hazard',
          objective: 'contain',
          progress: { current: 0.4, target: 1, label: 'Fire contained' },
          events: [{ id: 'event-2', kind: 'containment', message: 'Fire contained.', data: { amount: 0.2 } }],
        },
        dwellers,
      },
    })

    expect(wrapper.text()).toContain('ROOM HAZARD')
    expect(wrapper.text()).toContain('Fire contained')
    expect(wrapper.text()).toContain('+20%')
    expect(wrapper.text()).not.toContain('remaining')
  })
})
