import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { relationshipApi } from '@/modules/social/api/relationship'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const relationship = {
  id: 'rel-1',
  dweller_1_id: 'dweller-1',
  dweller_2_id: 'dweller-2',
  relationship_type: 'acquaintance',
  affinity: 50,
}

describe('relationshipApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads a vault relationship list', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: [relationship] })

    await expect(relationshipApi.getByVault('vault-1')).resolves.toEqual([relationship])
    expect(axios.get).toHaveBeenCalledWith('/api/v1/relationships/vault/vault-1')
  })

  it('loads one relationship', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: relationship })

    await expect(relationshipApi.get('rel-1')).resolves.toEqual(relationship)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/relationships/rel-1')
  })

  it('creates a relationship with a body', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: relationship })
    const payload = { dweller_1_id: 'dweller-1', dweller_2_id: 'dweller-2' }

    await expect(relationshipApi.create(payload)).resolves.toEqual(relationship)
    expect(axios.post).toHaveBeenCalledWith('/api/v1/relationships/', payload)
  })

  it('advances a relationship through romance, partnership and marriage', async () => {
    vi.mocked(axios.put).mockResolvedValue({ data: relationship })

    await relationshipApi.initiateRomance('rel-1')
    await relationshipApi.makePartners('rel-1')
    await relationshipApi.marry('rel-1')

    expect(axios.put).toHaveBeenNthCalledWith(1, '/api/v1/relationships/rel-1/romance', undefined)
    expect(axios.put).toHaveBeenNthCalledWith(2, '/api/v1/relationships/rel-1/partner', undefined)
    expect(axios.put).toHaveBeenNthCalledWith(3, '/api/v1/relationships/rel-1/marry', undefined)
  })

  it('breaks up through DELETE', async () => {
    vi.mocked(axios.delete).mockResolvedValue({ data: { message: 'Relationship ended' } })

    await expect(relationshipApi.breakUp('rel-1')).resolves.toEqual({
      message: 'Relationship ended',
    })
    expect(axios.delete).toHaveBeenCalledWith('/api/v1/relationships/rel-1')
  })

  it('loads a compatibility score', async () => {
    const score = { dweller_1_id: 'dweller-1', dweller_2_id: 'dweller-2', score: 0.75 }
    vi.mocked(axios.get).mockResolvedValue({ data: score })

    await expect(relationshipApi.getCompatibility('dweller-1', 'dweller-2')).resolves.toEqual(score)
    expect(axios.get).toHaveBeenCalledWith(
      '/api/v1/relationships/compatibility/dweller-1/dweller-2'
    )
  })

  it('processes vault breeding', async () => {
    const result = {
      stats: { relationships_updated: 2, conceptions: 1, births: 1, children_aged: 0 },
    }
    vi.mocked(axios.post).mockResolvedValue({ data: result })

    await expect(relationshipApi.processVaultBreeding('vault-1')).resolves.toEqual(result)
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/relationships/vault/vault-1/process',
      undefined
    )
  })
})
