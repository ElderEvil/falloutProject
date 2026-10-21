import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.fn()
const handleStoreError = vi.fn()

vi.mock('@/core/utils/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/core/utils/api')>()
  return { ...actual, apiGet: (...args: unknown[]) => apiGet(...args) }
})
vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
  handleStoreError,
}))

async function importComposable() {
  vi.resetModules()
  return import('@/core/composables/useGameBalance')
}

describe('useGameBalance', () => {
  beforeEach(() => {
    apiGet.mockReset()
    handleStoreError.mockReset()
  })

  afterEach(() => vi.restoreAllMocks())

  it('loads the live production rate from the balance response', async () => {
    apiGet.mockResolvedValue({ resource: { base_production_rate: 0.0012 } })
    const { useGameBalance } = await importComposable()

    const { baseProductionRate } = useGameBalance()
    await vi.waitFor(() => expect(baseProductionRate.value).toBe(0.0012))
    expect(apiGet).toHaveBeenCalledWith('/api/v1/game/balance')
  })

  it('retries after a transient failure and reports only the final error', async () => {
    apiGet
      .mockRejectedValueOnce(new Error('network'))
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ resource: { base_production_rate: 0.05 } })
    const { useGameBalance } = await importComposable()

    const { baseProductionRate } = useGameBalance()
    await vi.waitFor(() => expect(baseProductionRate.value).toBe(0.05))
    expect(apiGet).toHaveBeenCalledTimes(3)
    expect(handleStoreError).not.toHaveBeenCalled()
  })

  it('surfaces the error only after exhausting the attempts', async () => {
    apiGet.mockRejectedValue(new Error('down'))
    const { useGameBalance } = await importComposable()

    const { baseProductionRate } = useGameBalance()
    await vi.waitFor(() => expect(handleStoreError).toHaveBeenCalledTimes(1))
    expect(baseProductionRate.value).toBeNull()
    expect(apiGet).toHaveBeenCalledTimes(3)
  })

  it('reports a client error immediately without retrying', async () => {
    const { ApiError } = await import('@/core/utils/api')
    apiGet.mockRejectedValue(new ApiError({ message: 'Forbidden', status: 403 }))
    const { useGameBalance } = await importComposable()

    const { baseProductionRate } = useGameBalance()
    await vi.waitFor(() => expect(handleStoreError).toHaveBeenCalledTimes(1))
    expect(baseProductionRate.value).toBeNull()
    expect(apiGet).toHaveBeenCalledTimes(1)
  })

  it('retries a server error and recovers', async () => {
    const { ApiError } = await import('@/core/utils/api')
    apiGet
      .mockRejectedValueOnce(new ApiError({ message: 'Server error', status: 500 }))
      .mockResolvedValueOnce({ resource: { base_production_rate: 0.02 } })
    const { useGameBalance } = await importComposable()

    const { baseProductionRate } = useGameBalance()
    await vi.waitFor(() => expect(baseProductionRate.value).toBe(0.02))
    expect(apiGet).toHaveBeenCalledTimes(2)
    expect(handleStoreError).not.toHaveBeenCalled()
  })
})
