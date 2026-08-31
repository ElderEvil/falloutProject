import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useDwellerGenerationStore } from '@/modules/dwellers/stores/dwellerGeneration'

const toastError = vi.fn()

vi.mock('@/core/plugins/axios', () => ({
  default: { post: vi.fn() },
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: toastError }),
}))

vi.mock('@/modules/dwellers/stores/dwellerFilter', () => ({
  useDwellerFilterStore: () => ({ detailedDwellers: {} }),
}))

describe('useDwellerGenerationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows the API detail once when appearance generation fails', async () => {
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: {
        data: { detail: 'The AI provider returned an invalid appearance response. Please try again.' },
        status: 502,
      },
    })

    const result = await useDwellerGenerationStore().generateDwellerAppearance('dweller-1', 'token-1')

    expect(result).toBeNull()
    expect(toastError).toHaveBeenCalledTimes(1)
    expect(toastError).toHaveBeenCalledWith(
      'Failed to generate appearance for dweller dweller-1: The AI provider returned an invalid appearance response. Please try again.'
    )
  })

  it('extends an existing biography through the dedicated endpoint', async () => {
    vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'dweller-1', bio: 'An expanded biography.' } })

    const result = await useDwellerGenerationStore().extendDwellerBio('dweller-1', 'token-1')

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/dwellers/dweller-1/extend_bio/',
      null,
      expect.objectContaining({ headers: { Authorization: 'Bearer token-1' } })
    )
    expect(result).toEqual({ id: 'dweller-1', bio: 'An expanded biography.' })
  })
})
