import { afterEach, describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { createAxiosMock, createRouterMock, createToastMock } from '../helpers/mocks'
import { ref, effectScope, type EffectScope } from 'vue'
import { flushPromises } from '@vue/test-utils'

/**
 * Coverage for the live radio path.
 *
 * The legacy radio store (and its tests) were removed with the superseded
 * standalone route; `useRadioRoom` is what the room detail modal now drives, so
 * these pin the same contract behaviours: loading stats, switching mode, and
 * recruiting a dweller — including their error paths.
 */

const { get, put, post } = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), post: vi.fn() }))
vi.mock('@/core/plugins/axios', () => createAxiosMock({ get, put, post }))

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))

const authState = vi.hoisted(() => ({ token: 'test-token' as string | null }))
vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => authState }))

const vaultState = vi.hoisted(() => ({
  activeVault: { radio_mode: 'recruitment' },
  refreshVault: vi.fn(),
}))
vi.mock('@/modules/vault/stores/vault', () => ({ useVaultStore: () => vaultState }))

const dwellerState = vi.hoisted(() => ({ fetchDwellersByVault: vi.fn() }))
vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({ filter: dwellerState }),
}))

const toast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({ useToast: () => toast }))

vi.mock('@/modules/rooms/models/roomParts', () => ({ isRadioRoom: () => true }))

import { useRadioRoom } from '@/modules/rooms/composables/useRadioRoom'

const STATS_RESPONSE = {
  data: {
    has_radio: true,
    recruitment_rate: 0.1,
    rate_per_hour: 1.5,
    estimated_hours_per_recruit: 4,
    manual_cost_caps: 250,
    radio_mode: 'recruitment',
    radio_happiness_bonus: 0,
  },
}

const scopes: EffectScope[] = []

afterEach(() => {
  scopes.splice(0).forEach((scope) => scope.stop())
})

/** Mount the composable in a tracked scope; the suite stops them all after each test. */
function setup() {
  const scope = effectScope()
  scopes.push(scope)
  const api = scope.run(() =>
    useRadioRoom(ref({ id: 'room-1', name: 'Radio Studio' }) as never, ref(true), ref([]) as never)
  )
  if (!api) throw new Error('composable did not initialise')
  return api
}

beforeEach(() => {
  vi.clearAllMocks()
  authState.token = 'test-token'
  vaultState.activeVault = { radio_mode: 'recruitment' }
  vaultState.refreshVault.mockResolvedValue(undefined)
  dwellerState.fetchDwellersByVault.mockResolvedValue(undefined)
  get.mockResolvedValue(STATS_RESPONSE)
  put.mockResolvedValue({ data: {} })
  post.mockResolvedValue({ data: { message: 'Recruited!' } })
})

describe('useRadioRoom', () => {
  it('loads radio stats and the manual recruit cost when the room opens', async () => {
    const api = setup()
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/stats')
    expect(api.manualRecruitCost.value).toBe(250)
  })

  it('reports a stats load failure without throwing', async () => {
    get.mockRejectedValue(new Error('boom'))

    setup()
    await flushPromises()

    expect(toast.error).toHaveBeenCalledWith('Failed to load radio stats')
  })

  it('requires a token before loading stats', async () => {
    authState.token = null

    setup()
    await flushPromises()

    expect(toast.error).toHaveBeenCalledWith('Sign in is required to load radio stats')
    expect(get).not.toHaveBeenCalled()
  })

  it('switches the radio mode and confirms it', async () => {
    const api = setup()
    await flushPromises()

    await api.handleSwitchRadioMode('happiness')
    await flushPromises()

    expect(put).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/mode', undefined, {
      params: { mode: 'happiness' },
    })
    expect(api.localRadioMode.value).toBe('happiness')
    expect(toast.success).toHaveBeenCalledWith('Radio mode set to happiness')
  })

  it('reverts the optimistic mode when the switch fails', async () => {
    put.mockRejectedValue(new Error('nope'))

    const api = setup()
    await flushPromises()

    await api.handleSwitchRadioMode('happiness')
    await flushPromises()

    expect(api.localRadioMode.value).toBe('recruitment')
    expect(toast.error).toHaveBeenCalledWith('Failed to switch radio mode')
  })

  it('recruits a dweller and surfaces the server message', async () => {
    const api = setup()
    await flushPromises()

    await api.handleRecruitDweller()
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/recruit', {})
    expect(toast.success).toHaveBeenCalledWith('Recruited!')
    expect(api.isRecruiting.value).toBe(false)
  })

  it('refuses to recruit outside recruitment mode', async () => {
    vaultState.activeVault = { radio_mode: 'happiness' }

    const api = setup()
    await flushPromises()

    await api.handleRecruitDweller()

    expect(toast.error).toHaveBeenCalledWith('Radio must be in Recruitment mode')
    expect(post).not.toHaveBeenCalled()
  })

  it('surfaces the server detail when recruiting fails and clears the busy flag', async () => {
    post.mockRejectedValue({ response: { data: { detail: 'Insufficient caps' } } })

    const api = setup()
    await flushPromises()

    await api.handleRecruitDweller()
    await flushPromises()

    expect(toast.error).toHaveBeenCalledWith('Insufficient caps')
    expect(api.isRecruiting.value).toBe(false)
  })
})
