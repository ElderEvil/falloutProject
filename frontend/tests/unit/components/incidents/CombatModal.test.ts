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
})
