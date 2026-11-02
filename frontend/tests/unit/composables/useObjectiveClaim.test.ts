import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useObjectiveClaim } from '@/modules/progression/composables/useObjectiveClaim'
import type { Objective } from '@/modules/progression/models/objective'

vi.mock('@/core/plugins/axios')
vi.mock('@/core/composables/useSound', () => ({ useSound: () => ({ playSound: vi.fn() }) }))
vi.mock('@/modules/vault/composables/useNukaColaCount', () => ({
  refreshNukaColaCount: vi.fn().mockResolvedValue(undefined),
}))

const objective = {
  id: 'objective-1',
  category: 'daily',
  progress: 0,
  total: 1,
  is_completed: false,
} as Objective

describe('useObjectiveClaim', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'token-1'
    useVaultStore().gameState = { is_paused: true }
  })

  it('refreshes the vault caps and roster after a successful claim', async () => {
    useObjectivesStore().objectives = [objective]
    const dwellers = useDwellerFilterStore()
    const vault = useVaultStore()

    vi.mocked(axios.post).mockImplementation(async (url) => {
      if (String(url).includes('/claim')) {
        return { data: { progress: 1, total: 1, is_completed: true } }
      }
      return { data: {} }
    })
    vi.mocked(axios.get).mockImplementation(async (url) => {
      const target = String(url)
      if (target.startsWith('/api/v1/vaults/')) {
        return { data: { id: 'vault-1', bottle_caps: 750 } }
      }
      if (target.startsWith('/api/v1/dwellers/vault/')) {
        return { data: [{ id: 'dweller-1', first_name: 'Lucy', health: 90 }] }
      }
      return { data: [] }
    })

    await useObjectiveClaim({ value: 'vault-1' }).claim('objective-1')

    await vi.waitFor(() => {
      expect(vault.loadedVaults['vault-1']?.bottle_caps).toBe(750)
      expect(dwellers.dwellers).toEqual([
        expect.objectContaining({ id: 'dweller-1', health: 90 }),
      ])
    })
  })

  it('does not refresh the vault or roster when the claim fails', async () => {
    useObjectivesStore().objectives = [objective]
    vi.mocked(axios.post).mockRejectedValue({ response: { status: 409, data: { detail: 'Gone' } } })

    const actions = useObjectiveClaim({ value: 'vault-1' })
    await actions.claim('objective-1')

    expect(actions.error.value).toBe('Gone')
    expect(axios.get).not.toHaveBeenCalled()
  })
})
