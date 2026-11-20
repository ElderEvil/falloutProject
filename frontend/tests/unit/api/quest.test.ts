import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from '@/core/plugins/axios'
import { listVaultQuests } from '@/modules/progression/api/quest'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const questRead = (id: string) => ({
  id,
  title: `Quest ${id}`,
  short_description: 'Fixture quest',
  long_description: 'Pagination fixture',
  requirements: 'No prerequisites',
  rewards: '10 caps',
  quest_type: 'side',
  is_visible: true,
  is_locked: false,
  is_completed: false,
  is_reward_ready: false,
})

describe('questApi.listVaultQuests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps fetching until the catalog is exhausted beyond row 100', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => questRead(`q-${index}`))
    const secondPage = [questRead('q-tail')]
    vi.mocked(axios.get)
      .mockResolvedValueOnce({ data: firstPage })
      .mockResolvedValueOnce({ data: secondPage })

    const quests = await listVaultQuests('vault-1')

    expect(quests).toHaveLength(101)
    expect(quests.at(-1)?.id).toBe('q-tail')
    expect(axios.get).toHaveBeenCalledTimes(2)
    expect(axios.get).toHaveBeenNthCalledWith(2, '/api/v1/quests/vault-1/', {
      params: { skip: 100, limit: 100 },
    })
  })

  it('raises when the endpoint does not answer with a list', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { unexpected: true } })

    await expect(listVaultQuests('vault-1')).rejects.toThrow(TypeError)
  })
})
