import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useExplorationFinish } from '@/modules/exploration/composables/useExplorationFinish'
import type { Exploration } from '@/modules/exploration/stores/exploration'

vi.mock('@/core/plugins/axios')

const exploration = {
  id: 'exploration-1',
  dweller_id: 'dweller-1',
} as Exploration

describe('useExplorationFinish', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'token-1'
    useVaultStore().gameState = { is_paused: true }
    useExplorationStore().activeExplorations['exploration-1'] = exploration
  })

  it('refreshes the vault caps and roster after a completed exploration', async () => {
    const dwellers = useDwellerFilterStore()
    const vault = useVaultStore()

    vi.mocked(axios.get).mockImplementation(async (url) => {
      const target = String(url)
      if (target.startsWith('/api/v1/vaults/')) {
        return { data: { id: 'vault-1', bottle_caps: 1250 } }
      }
      if (target.startsWith('/api/v1/dwellers/vault/')) {
        return { data: [{ id: 'dweller-1', first_name: 'Lucy', health: 80 }] }
      }
      return { data: [] }
    })

    const finish = useExplorationFinish(() => 'vault-1')
    await finish.finishExploration(
      'exploration-1',
      async () => ({ rewards_summary: null }),
      'Failed to finish exploration'
    )

    expect(vault.loadedVaults['vault-1']?.bottle_caps).toBe(1250)
    expect(dwellers.dwellers).toEqual([expect.objectContaining({ id: 'dweller-1', health: 80 })])
  })

  it('does not refresh when the finish action fails', async () => {
    const finish = useExplorationFinish(() => 'vault-1')

    await finish.finishExploration(
      'exploration-1',
      async () => {
        throw new Error('offline')
      },
      'Failed to finish exploration'
    )

    expect(axios.get).not.toHaveBeenCalled()
  })
})
