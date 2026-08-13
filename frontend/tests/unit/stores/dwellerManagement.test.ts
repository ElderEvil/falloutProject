import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useDwellerManagementStore } from '@/modules/dwellers/stores/dwellerManagement'

vi.mock('@/core/plugins/axios', () => ({
  default: {
    post: vi.fn(),
  },
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

describe('useDwellerManagementStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('assigns only available dwellers to production rooms and refreshes the list', async () => {
    const filterStore = useDwellerFilterStore()
    const managementStore = useDwellerManagementStore()
    const refreshSpy = vi.spyOn(filterStore, 'fetchDwellersByVault').mockResolvedValue()
    vi.mocked(axios.post).mockResolvedValue({
      data: { assigned_count: 2, assignments: [] },
    })

    const result = await managementStore.autoAssignProductionDwellers('vault-1', 'token-1')

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/vaults/vault-1/dwellers/auto-assign-production',
      null,
      { headers: { Authorization: 'Bearer token-1' } }
    )
    expect(refreshSpy).toHaveBeenCalledWith('vault-1', 'token-1')
    expect(result).toEqual({ assigned_count: 2, assignments: [] })
  })
})
