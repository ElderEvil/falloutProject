import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useDwellerMedicalStore } from '@/modules/dwellers/stores/dwellerMedical'

const toastMock = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))

vi.mock('@/core/plugins/axios', () => ({
  default: {
    post: vi.fn(),
  },
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => toastMock,
}))

describe('useDwellerMedicalStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('treats irradiated dwellers, refreshes the roster, and reports the supplies used', async () => {
    const filterStore = useDwellerFilterStore()
    const medicalStore = useDwellerMedicalStore()
    const refreshSpy = vi.spyOn(filterStore, 'fetchDwellersByVault').mockResolvedValue()
    const payload = {
      dwellers_treated: 3,
      radaways_used: 3,
      stimpaks_used: 3,
      vault_radaways: 7,
      vault_stimpacks: 7,
    }
    vi.mocked(axios.post).mockResolvedValue({ data: payload })

    const result = await medicalStore.distributeRecoverySupplies('vault-1', 'token-1')

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/storage/vault/vault-1/medical/distribute-recovery-supplies',
      null,
      { headers: { Authorization: 'Bearer token-1' } }
    )
    expect(refreshSpy).toHaveBeenCalledWith('vault-1', 'token-1')
    expect(result).toEqual(payload)
    expect(toastMock.success).toHaveBeenCalledWith('Treated 3 dwellers with 3 RadAway and 3 Stimpack')
  })

  it('reports nothing to do when no dweller was irradiated', async () => {
    const filterStore = useDwellerFilterStore()
    const medicalStore = useDwellerMedicalStore()
    vi.spyOn(filterStore, 'fetchDwellersByVault').mockResolvedValue()
    vi.mocked(axios.post).mockResolvedValue({
      data: {
        dwellers_treated: 0,
        radaways_used: 0,
        stimpaks_used: 0,
        vault_radaways: 12,
        vault_stimpacks: 12,
      },
    })

    await medicalStore.distributeRecoverySupplies('vault-1', 'token-1')

    expect(toastMock.info).toHaveBeenCalledWith('No irradiated dwellers needed treatment')
  })

  it('surfaces the failure and returns null when the request fails', async () => {
    const filterStore = useDwellerFilterStore()
    const medicalStore = useDwellerMedicalStore()
    vi.spyOn(filterStore, 'fetchDwellersByVault').mockResolvedValue()
    vi.mocked(axios.post).mockRejectedValue(new Error('boom'))

    const result = await medicalStore.distributeRecoverySupplies('vault-1', 'token-1')

    expect(result).toBeNull()
  })
})
