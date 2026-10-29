import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { pregnancyApi } from '@/modules/social/api/pregnancy'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

const pregnancy = {
  id: 'preg-1',
  mother_id: 'mother-1',
  father_id: 'father-1',
  status: 'pregnant',
  progress_percentage: 40,
  time_remaining_seconds: 600,
  is_due: false,
}

describe('pregnancyApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads a vault pregnancy list', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: [pregnancy] })

    await expect(pregnancyApi.getByVault('vault-1')).resolves.toEqual([pregnancy])
    expect(axios.get).toHaveBeenCalledWith('/api/v1/pregnancies/vault/vault-1')
  })

  it('loads one pregnancy', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: pregnancy })

    await expect(pregnancyApi.get('preg-1')).resolves.toEqual(pregnancy)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/pregnancies/preg-1')
  })

  it('delivers a pregnancy', async () => {
    const result = { pregnancy_id: 'preg-1', children: [], message: 'A child is born' }
    vi.mocked(axios.post).mockResolvedValue({ data: result })

    await expect(pregnancyApi.deliver('preg-1')).resolves.toEqual(result)
    expect(axios.post).toHaveBeenCalledWith('/api/v1/pregnancies/preg-1/deliver', undefined)
  })
})
