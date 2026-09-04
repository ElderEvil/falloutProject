import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import GameControlPanel from '@/modules/vault/components/shell/GameControlPanel.vue'

const vaultStore = {
  gameState: null,
  isLoading: false,
  fetchGameState: vi.fn(),
  startResourcePolling: vi.fn(),
  stopResourcePolling: vi.fn(),
  pauseVault: vi.fn(),
  resumeVault: vi.fn(),
}

const authStore = {
  token: 'test-token',
  user: { is_superuser: true },
}

const incidentStore = {
  spawnDebugIncident: vi.fn(),
}

vi.mock('@/modules/vault/stores/vault', () => ({ useVaultStore: () => vaultStore }))
vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => authStore }))
vi.mock('@/modules/combat/stores/incident', () => ({ useIncidentStore: () => incidentStore }))
vi.mock('@/core/utils/errorHandler', () => ({ handleStoreError: vi.fn() }))
vi.mock('@iconify/vue', () => ({ Icon: { template: '<span />' } }))

describe('GameControlPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps pause and spawn controls inside the panel box', () => {
    const wrapper = mount(GameControlPanel, { props: { vaultId: 'vault-1' } })
    const panel = wrapper.find('div')

    expect(panel.classes()).toContain('flex-wrap')
    expect(panel.classes()).toContain('max-w-[calc(100vw-2rem)]')
    expect(panel.classes()).toContain('fixed')
    expect(wrapper.find('.game-control-actions').exists()).toBe(true)
  })

  it('offers each incident type to superusers for targeted UI testing', async () => {
    const wrapper = mount(GameControlPanel, { props: { vaultId: 'vault-1' } })

    expect(wrapper.findAll('.admin-incident-button')).toHaveLength(7)
    await wrapper.get('[title="Spawn Fire incident"]').trigger('click')

    expect(incidentStore.spawnDebugIncident).toHaveBeenCalledWith('vault-1', 'test-token', 'fire')
  })
})
