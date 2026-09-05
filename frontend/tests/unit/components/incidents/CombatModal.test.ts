import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import CombatModal from '@/modules/combat/components/incidents/CombatModal.vue'

const incidentStore = vi.hoisted(() => ({ fetchIncidents: vi.fn(), getIncidentById: vi.fn() }))
const incidentApiMock = vi.hoisted(() => ({ getIncident: vi.fn() }))
const medicalStore = vi.hoisted(() => ({
  useStimpack: vi.fn(),
  useRadaway: vi.fn(),
  issueMedicalSupply: vi.fn(),
}))
const vaultStore = vi.hoisted(() => ({
  loadedVaults: {} as Record<string, { stimpack: number; radaway: number }>,
}))
const routerPush = vi.hoisted(() => vi.fn())
const toastError = vi.hoisted(() => vi.fn())

vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => ({ token: 'test-token' }) }))
vi.mock('@/modules/combat/stores/incident', () => ({ useIncidentStore: () => incidentStore }))
vi.mock('@/modules/combat/api/incident', () => ({ incidentApi: incidentApiMock }))
vi.mock('@/modules/dwellers/stores/dwellerMedical', () => ({
  useDwellerMedicalStore: () => medicalStore,
}))
vi.mock('@/modules/vault/stores/vault', () => ({ useVaultStore: () => vaultStore }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))
vi.mock('@/core/composables/useToast', () => ({ useToast: () => ({ error: toastError }) }))
vi.mock('@/core/composables/usePolling', () => ({ usePolling: vi.fn() }))
vi.mock('@iconify/vue', () => ({ Icon: { template: '<span />' } }))

const baseIncident = {
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
  events: [],
}

function mountModal(dwellers: unknown[] = [], extraProps: Record<string, unknown> = {}) {
  return mount(CombatModal, {
    props: {
      incidentId: 'incident-1',
      vaultId: 'vault-1',
      dwellers: dwellers as never[],
      ...extraProps,
    },
    global: {
      stubs: {
        UModal: { template: '<div><slot name="header" /><slot /></div>' },
        UAlert: { template: '<div><slot /></div>' },
        UButton: {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
        UProgressBar: true,
        ComponentLoader: true,
        IncidentStage: true,
        DwellerPortrait: { template: '<span />' },
      },
    },
  })
}

function healthyDweller(overrides = {}) {
  return {
    id: 'dweller-1',
    first_name: 'Nora',
    last_name: 'Vance',
    is_adult: true,
    health: 100,
    max_health: 100,
    radiation: 0,
    level: 8,
    room_id: 'room-2',
    status: 'idle',
    thumbnail_url: null,
    stimpack: 0,
    ...overrides,
  }
}

describe('CombatModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vaultStore.loadedVaults = {}
    incidentStore.fetchIncidents.mockResolvedValue(undefined)
    incidentStore.getIncidentById.mockReturnValue({ ...baseIncident })
    incidentApiMock.getIncident.mockRejectedValue(new Error('not found'))
  })

  it('offers a retry when incident loading fails', async () => {
    incidentStore.fetchIncidents.mockRejectedValueOnce(new Error('offline'))
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Unable to load incident data.')
    const requestsBeforeRetry = incidentStore.fetchIncidents.mock.calls.length
    await wrapper.get('button').trigger('click')
    expect(incidentStore.fetchIncidents).toHaveBeenCalledTimes(requestsBeforeRetry + 1)
  })

  it('renders journal and rewards as collapsed sections with the journal first', async () => {
    incidentStore.getIncidentById.mockReturnValue({
      ...baseIncident,
      loot: { caps: 100, items: [] },
      events: [
        {
          id: 'event-1',
          kind: 'round',
          message: 'Responders exchanged fire.',
          data: { damage_to_threat: 12, damage_to_dwellers: 3 },
        },
      ],
    })
    const wrapper = mountModal()
    await flushPromises()

    const sections = wrapper.findAll('details.section')
    expect(sections.length).toBe(3)
    expect(sections[0].find('summary').text()).toContain('Response team (0)')
    expect(sections[1].find('summary').text()).toContain('Incident journal')
    expect(sections[2].find('summary').text()).toContain('Rewards')
    expect(wrapper.text().indexOf('Incident journal')).toBeLessThan(
      wrapper.text().indexOf('Rewards')
    )
    expect(wrapper.text()).toContain('Damage dealt: 12 · Damage taken: 3')
    expect(wrapper.text()).not.toContain('EXPECTED REWARDS')
  })

  it('renders cumulative progress and elapsed times for journal entries', async () => {
    incidentStore.getIncidentById.mockReturnValue({
      ...baseIncident,
      start_time: '2026-09-05T00:00:00',
      events: [
        {
          id: 'event-1',
          kind: 'round',
          message: 'Round: dealt 12 damage (2/8 down); took 3.',
          data: {
            damage_to_threat: 12,
            damage_to_dwellers: 3,
            enemies_defeated: 2,
            expected_threat: 8,
          },
          created_at: '2026-09-05T00:01:30',
        },
      ],
    })
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Dealt 12 damage (2/8 down) · took 3')
    const local = new Date('2026-09-05T00:01:30Z')
    const label = `${String(local.getHours()).padStart(2, '0')}:${String(local.getMinutes()).padStart(2, '0')}`
    expect(wrapper.text()).toContain(label)
  })

  it('rounds fractional damage in journal entries', async () => {
    incidentStore.getIncidentById.mockReturnValue({
      ...baseIncident,
      events: [
        {
          id: 'event-1',
          kind: 'round',
          message: 'Round.',
          data: {
            damage_to_threat: 1.7600000000000002,
            damage_to_dwellers: 6,
            enemies_defeated: 2,
            expected_threat: 6,
          },
        },
      ],
    })
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Dealt 2 damage (2/6 down) · took 6')
  })

  it('opens dweller details when a responder name is clicked', async () => {
    const wrapper = mountModal([healthyDweller()])
    await flushPromises()

    await wrapper.get('button.responder-name').trigger('click')
    expect(routerPush).toHaveBeenCalledWith({
      name: 'dwellerDetail',
      params: { id: 'vault-1', dwellerId: 'dweller-1' },
    })
  })

  it('heals with a carried stimpak without touching vault storage', async () => {
    medicalStore.useStimpack.mockResolvedValue({ id: 'dweller-9' })
    const wrapper = mountModal([healthyDweller({ id: 'dweller-9', health: 40, stimpack: 2 })])
    await flushPromises()

    const healButton = wrapper.findAll('button').find((button) => button.text().includes('HEAL'))
    expect(healButton).toBeTruthy()
    await healButton!.trigger('click')

    expect(medicalStore.issueMedicalSupply).not.toHaveBeenCalled()
    expect(medicalStore.useStimpack).toHaveBeenCalledWith('dweller-9', 'test-token')
  })

  it('issues a stimpak from vault storage before healing when direct use fails', async () => {
    vaultStore.loadedVaults = { 'vault-1': { stimpack: 3, radaway: 1 } }
    medicalStore.issueMedicalSupply.mockResolvedValue({ stimpaks: 1 })
    medicalStore.useStimpack.mockResolvedValueOnce(null).mockResolvedValue({ id: 'dweller-9' })
    const wrapper = mountModal([healthyDweller({ id: 'dweller-9', health: 40, stimpack: 0 })])
    await flushPromises()

    const healButton = wrapper.findAll('button').find((button) => button.text().includes('HEAL'))
    expect(healButton).toBeTruthy()
    await healButton!.trigger('click')

    expect(medicalStore.issueMedicalSupply).toHaveBeenCalledWith(
      'vault-1',
      'dweller-9',
      'stimpack',
      'test-token'
    )
    expect(medicalStore.useStimpack).toHaveBeenCalledWith('dweller-9', 'test-token')
  })

  it('attempts direct use without vault fallback when vault storage is empty', async () => {
    medicalStore.useStimpack.mockResolvedValue(null)
    const wrapper = mountModal([healthyDweller({ id: 'dweller-9', health: 40, stimpack: 0 })])
    await flushPromises()

    const healButton = wrapper.findAll('button').find((button) => button.text().includes('HEAL'))
    expect(healButton).toBeTruthy()
    await healButton!.trigger('click')

    expect(medicalStore.useStimpack).toHaveBeenCalledWith('dweller-9', 'test-token')
    expect(medicalStore.issueMedicalSupply).not.toHaveBeenCalled()
  })

  it('treats radiation with RadAway, issuing from vault when direct use fails', async () => {
    vaultStore.loadedVaults = { 'vault-1': { stimpack: 3, radaway: 2 } }
    medicalStore.issueMedicalSupply.mockResolvedValue({ radaways: 1 })
    medicalStore.useRadaway.mockResolvedValueOnce(null).mockResolvedValue({ id: 'dweller-9' })
    const wrapper = mountModal([healthyDweller({ id: 'dweller-9', radiation: 60 })])
    await flushPromises()

    const radButton = wrapper.findAll('button').find((button) => button.text().includes('RAD'))
    expect(radButton).toBeTruthy()
    await radButton!.trigger('click')

    expect(medicalStore.issueMedicalSupply).toHaveBeenCalledWith(
      'vault-1',
      'dweller-9',
      'radaway',
      'test-token'
    )
    expect(medicalStore.useRadaway).toHaveBeenCalledWith('dweller-9', 'test-token')
  })

  it('renders a preview incident without touching the store', async () => {
    const wrapper = mountModal([], {
      previewIncident: { ...baseIncident, type: 'deathclaw_attack' } as never,
      previewVaultMedical: { stimpack: 5, radaway: 3 },
      preview: true,
    })
    await flushPromises()

    expect(incidentStore.fetchIncidents).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('DEATHCLAW ATTACK')
  })

  it.each([
    ['resolved', 'INCIDENT RESOLVED'],
    ['failed', 'INCIDENT FAILED'],
  ])('renders %s preview incidents in the terminal result view', async (status, result) => {
    const wrapper = mountModal([], {
      previewIncident: { ...baseIncident, status } as never,
      preview: true,
    })
    await flushPromises()

    expect(wrapper.text()).toContain(result)
    expect(wrapper.text()).not.toContain('Response team')
  })

  it('disables treatments in preview mode', async () => {
    const wrapper = mountModal([healthyDweller({ id: 'dweller-9', health: 40 })], {
      previewIncident: { ...baseIncident } as never,
      preview: true,
    })
    await flushPromises()

    const healButton = wrapper.findAll('button').find((button) => button.text().includes('HEAL'))
    expect(healButton).toBeTruthy()
    expect(healButton!.attributes('disabled')).toBeDefined()
    expect(healButton!.attributes('title')).toContain('Preview')
    await healButton!.trigger('click')
    expect(medicalStore.useStimpack).not.toHaveBeenCalled()
  })

  it('shows the victory state with loot when the incident resolves', async () => {
    incidentStore.getIncidentById.mockReturnValue(undefined)
    incidentApiMock.getIncident.mockResolvedValue({
      ...baseIncident,
      status: 'resolved',
      loot: {
        caps: 250,
        items: [{ type: 'weapon', name: 'Rusty Laser Pistol', rarity: 'rare', quantity: 1 }],
      },
    })
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('INCIDENT RESOLVED')
    expect(wrapper.text()).toContain('Recovered 250 caps')
    expect(wrapper.text()).toContain('Rusty Laser Pistol')
    expect(wrapper.text()).not.toContain('Response team')
    const closeButton = wrapper.findAll('button').find((button) => button.text() === 'CLOSE')
    expect(closeButton).toBeTruthy()
    await closeButton!.trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('shows the defeat state when the incident fails', async () => {
    incidentStore.getIncidentById.mockReturnValue(undefined)
    incidentApiMock.getIncident.mockResolvedValue({
      ...baseIncident,
      status: 'failed',
      damage_dealt: 180,
    })
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('INCIDENT FAILED')
    expect(wrapper.text()).toContain('overrun')
  })

  it('offers a retry when a vanished incident cannot be recovered', async () => {
    incidentStore.getIncidentById.mockReturnValue(undefined)
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Unable to load incident data.')
  })
})
