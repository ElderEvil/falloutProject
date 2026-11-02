import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createAxiosMock, createToastMock } from '../helpers/mocks'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useDwellerMedicalStore } from '@/modules/dwellers/stores/dwellerMedical'

const toastMock = createToastMock()

vi.mock('@/core/plugins/axios', () => createAxiosMock())

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => toastMock,
}))

describe('useDwellerMedicalStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('treats irradiated dwellers, loads the treated roster, and reports the supplies used', async () => {
    const filterStore = useDwellerFilterStore()
    const medicalStore = useDwellerMedicalStore()
    const payload = {
      dwellers_treated: 3,
      radaways_used: 3,
      stimpaks_used: 3,
      vault_radaways: 7,
      vault_stimpacks: 7,
    }
    vi.mocked(axios.post).mockResolvedValue({ data: payload })
    vi.mocked(axios.get).mockResolvedValue({ data: [{ id: 'd1', radiation: 0 }] })

    const result = await medicalStore.distributeRecoverySupplies('vault-1', 'token-1')

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/storage/vault/vault-1/medical/distribute-recovery-supplies',
      null,
      { headers: { Authorization: 'Bearer token-1' } }
    )
    expect(result).toEqual(payload)
    expect(filterStore.dwellers).toEqual([{ id: 'd1', radiation: 0 }])
    expect(filterStore.allDwellers).toEqual([{ id: 'd1', radiation: 0 }])
    expect(toastMock.success).toHaveBeenCalledWith(
      'Treated 3 dwellers with 3 RadAway and 3 Stimpack'
    )
  })

  it.each([
    ['stimpack', 'useStimpack', { health: 100, stimpack: 0 }],
    ['radaway', 'useRadaway', { radiation: 0, radaway: 0 }],
  ] as const)('patches the roster and detail cache after using a %s', async (supply, action, change) => {
    const filter = useDwellerFilterStore()
    const medical = useDwellerMedicalStore()
    filter.dwellers = [
      { id: 'd1', health: 40, radiation: 60, stimpack: 1, radaway: 1 },
      { id: 'd2', health: 10, radiation: 90, stimpack: 0, radaway: 0 },
    ] as never
    filter.detailedDwellers.d1 = { id: 'd1', health: 40, radiation: 60, name: 'Ann' } as never
    vi.mocked(axios.post).mockResolvedValue({ data: { id: 'd1', ...change } })

    const result = await medical[action]('d1', 'token-1')

    expect(axios.post).toHaveBeenCalledWith(`/api/v1/dwellers/d1/use_${supply}`, null, {
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(result).toMatchObject(change)
    expect(filter.dwellers[0]).toMatchObject(change)
    expect(filter.dwellers[1]).toMatchObject({ id: 'd2', health: 10, radiation: 90 })
    expect(filter.detailedDwellers.d1).toMatchObject({ ...change, name: 'Ann' })
  })

  it('reports healing once when a supply must first be issued from storage', async () => {
    const medical = useDwellerMedicalStore()
    vi.mocked(axios.post)
      .mockResolvedValueOnce({ data: { dweller_stimpacks: 1 } })
      .mockResolvedValueOnce({ data: { id: 'd1', health: 100, stimpack: 0 } })
    await medical.issueMedicalSupply('vault-1', 'd1', 'stimpack', 'token')
    await medical.useStimpack('d1', 'token')
    expect(toastMock.success).toHaveBeenCalledTimes(1)
    expect(toastMock.success).toHaveBeenCalledWith('Stimpack used! Dweller healed.')
  })

  it('refreshes recovery results even when a pre-treatment roster is still loading', async () => {
    const filter = useDwellerFilterStore()
    const medical = useDwellerMedicalStore()
    vi.spyOn(filter, 'fetchDwellersByVault').mockResolvedValue()
    let finishOld!: (value: unknown) => void
    vi.mocked(axios.get)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishOld = resolve
          })
      )
      .mockResolvedValueOnce({ data: [{ id: 'treated', radiation: 0 }] })
    const old = filter.fetchAllDwellers('vault-1', 'token-1')
    vi.mocked(axios.post).mockResolvedValue({
      data: { dwellers_treated: 1, radaways_used: 1, stimpaks_used: 0 },
    })
    const treatment = medical.distributeRecoverySupplies('vault-1', 'token-1')
    await flushPromises()
    finishOld({ data: [{ id: 'treated', radiation: 50 }] })
    await Promise.all([old, treatment])
    expect(axios.get).toHaveBeenCalledTimes(2)
    expect(filter.allDwellers[0].radiation).toBe(0)
  })

  it('reports nothing to do when no dweller was irradiated', async () => {
    const medicalStore = useDwellerMedicalStore()
    vi.mocked(axios.get).mockResolvedValue({ data: [] })
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
    filterStore.dwellers = [{ id: 'd1', radiation: 50 }] as never
    const medicalStore = useDwellerMedicalStore()
    vi.mocked(axios.post).mockRejectedValue(new Error('boom'))

    const result = await medicalStore.distributeRecoverySupplies('vault-1', 'token-1')

    expect(result).toBeNull()
    expect(axios.get).not.toHaveBeenCalled()
    expect(filterStore.dwellers).toEqual([{ id: 'd1', radiation: 50 }])
  })

  it('emits one detail-only toast when using a stimpack fails', async () => {
    const medicalStore = useDwellerMedicalStore()
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'No stimpacks available' } },
    })

    const result = await medicalStore.useStimpack('d1', 'token-1')

    expect(result).toBeNull()
    expect(toastMock.error).toHaveBeenCalledTimes(1)
    expect(toastMock.error).toHaveBeenCalledWith('No stimpacks available')
  })
})
