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

    expect(panel.classes()).toContain('flex-nowrap')
    expect(panel.classes()).toContain('overflow-x-auto')
    expect(panel.classes()).toContain('max-w-[calc(100vw-2rem)]')
    expect(panel.classes()).toContain('fixed')
    expect(panel.classes()).toContain('left-1/2')
    expect(panel.classes()).toContain('-translate-x-1/2')
    expect(panel.classes()).not.toContain('right-4')
    expect(wrapper.find('.game-control-actions').exists()).toBe(true)
    expect(wrapper.find('.game-control-actions').classes()).toContain('flex-nowrap')
  })

  it('offers each incident type to superusers for targeted UI testing', async () => {
    const wrapper = mount(GameControlPanel, { props: { vaultId: 'vault-1' } })

    expect(wrapper.findAll('.admin-incident-button')).toHaveLength(7)
    expect(wrapper.find('.admin-incident-button span.hidden').exists()).toBe(true)
    await wrapper.get('[title="Spawn Fire incident"]').trigger('click')

    expect(incidentStore.spawnDebugIncident).toHaveBeenCalledWith('vault-1', 'test-token', 'fire')
  })
})
