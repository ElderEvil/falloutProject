import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import axios from '@/core/plugins/axios'
import { getRadioStats, recruitDweller, setRadioMode } from '@/modules/radio/api/radio'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}))

describe('setRadioMode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('switches the vault radio mode through the query parameter', async () => {
    ;(axios.put as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { radio_mode: 'happiness' },
    })

    const result = await setRadioMode('vault-1', 'happiness')

    expect(axios.put).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/mode', undefined, {
      params: { mode: 'happiness' },
    })
    expect(result).toBe('happiness')
  })

  it('propagates a failure so the caller can surface it', async () => {
    ;(axios.put as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('nope'))

    await expect(setRadioMode('vault-1', 'recruitment')).rejects.toThrow('nope')
  })

  it('reads radio stats through the module boundary', async () => {
    const stats = { has_radio: true, manual_cost_caps: 250 }
    ;(axios.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: stats })

    await expect(getRadioStats('vault-1')).resolves.toEqual(stats)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/stats')
  })

  it('recruits a dweller through the query-free recruit endpoint', async () => {
    const response = { message: 'Recruited!', recycled: false }
    ;(axios.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: response })

    await expect(recruitDweller('vault-1')).resolves.toEqual(response)
    expect(axios.post).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/recruit', {})
  })
})
