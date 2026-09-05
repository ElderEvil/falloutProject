import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import CombatModal from '@/modules/combat/components/incidents/CombatModal.vue'

const incidentStore = vi.hoisted(() => ({ fetchIncidents: vi.fn(), getIncidentById: vi.fn() }))

vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => ({ token: 'test-token' }) }))
vi.mock('@/modules/combat/stores/incident', () => ({ useIncidentStore: () => incidentStore }))
vi.mock('@/core/composables/useToast', () => ({ useToast: () => ({ error: vi.fn() }) }))
vi.mock('@/core/composables/usePolling', () => ({ usePolling: vi.fn() }))
vi.mock('@iconify/vue', () => ({ Icon: { template: '<span />' } }))

describe('CombatModal', () => {
  it('offers a retry when incident loading fails', async () => {
    incidentStore.fetchIncidents.mockRejectedValueOnce(new Error('offline'))
    const wrapper = mount(CombatModal, {
      props: { incidentId: 'incident-1', vaultId: 'vault-1', dwellers: [] },
      global: {
        stubs: {
          UModal: { template: '<div><slot name="header" /><slot /></div>' },
          UAlert: { template: '<div><slot /></div>' },
          UButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
          UProgressBar: true,
          ComponentLoader: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Unable to load incident data.')
    const requestsBeforeRetry = incidentStore.fetchIncidents.mock.calls.length
    await wrapper.get('button').trigger('click')
    expect(incidentStore.fetchIncidents).toHaveBeenCalledTimes(requestsBeforeRetry + 1)
  })

  it('places the incident journal before expected rewards', async () => {
    incidentStore.fetchIncidents.mockResolvedValue(undefined)
    incidentStore.getIncidentById.mockReturnValue({
      id: 'incident-1',
      room_id: 'room-1',
      room_name: 'Power Generator',
      type: 'raider_attack',
      status: 'active',
      difficulty: 3,
      elapsed_time: 10,
      damage_dealt: 0,
      rooms_affected: ['room-1'],
      spread_count: 0,
      loot: null,
      family: 'intrusion',
      objective: 'defeat',
      progress: { current: 1, target: 6, label: 'Intruders neutralized' },
      risk: { kind: 'breach', rooms_affected: 1 },
      response: { label: 'Send defenders' },
      events: [
        {
          id: 'event-1',
          kind: 'round',
          message: 'Responders exchanged fire.',
          data: { damage_to_threat: 12, damage_to_dwellers: 3 },
        },
      ],
    })
    const wrapper = mount(CombatModal, {
      props: { incidentId: 'incident-1', vaultId: 'vault-1', dwellers: [] },
      global: {
        stubs: { UModal: { template: '<div><slot name="header" /><slot /></div>' }, UBadge: true, UProgressBar: true, IncidentStage: true },
      },
    })
    await flushPromises()

    expect(wrapper.text().indexOf('INCIDENT JOURNAL')).toBeLessThan(wrapper.text().indexOf('EXPECTED REWARDS'))
    expect(wrapper.text()).toContain('Damage dealt: 12 · Damage taken: 3')
  })
})
