import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { setRadioMode } from '@/modules/radio/api/radio'

vi.mock('@/core/plugins/axios', () => ({
  default: { put: vi.fn() },
}))

describe('setRadioMode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('switches the vault radio mode through the query parameter', async () => {
    ;(axios.put as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { radio_mode: 'happiness' } })

    const result = await setRadioMode('vault-1', 'happiness')

    expect(axios.put).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/mode', null, {
      params: { mode: 'happiness' },
    })
    expect(result).toBe('happiness')
  })

  it('propagates a failure so the caller can surface it', async () => {
    ;(axios.put as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('nope'))

    await expect(setRadioMode('vault-1', 'recruitment')).rejects.toThrow('nope')
  })
})
