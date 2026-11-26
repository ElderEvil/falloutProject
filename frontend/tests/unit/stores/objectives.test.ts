import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import axios from '@/core/plugins/axios'
import type { Objective } from '@/modules/progression/models/objective'

vi.mock('@/core/plugins/axios')

const objective = (overrides: Record<string, unknown> = {}) =>
  ({
    id: '1',
    challenge: 'Collect 100 caps',
    progress: 50,
    total: 100,
    reward: '50 caps',
    is_completed: false,
    ...overrides,
  }) as unknown as Objective

const fetchParams = { params: { skip: 0, limit: 100 } }

describe('Objectives Store', () => {
  let objectivesStore: ReturnType<typeof useObjectivesStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    objectivesStore = useObjectivesStore()
    vi.clearAllMocks()
  })

  it('should initialize with empty objectives array', () => {
    expect(objectivesStore.objectives).toEqual([])
  })

  describe('fetchObjectives Action', () => {
    it('should fetch objectives successfully', async () => {
      const mockObjectives = [
        objective(),
        objective({ id: '2', challenge: 'Build 5 rooms', progress: 3, total: 5 }),
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockObjectives })

      await objectivesStore.fetchObjectives('vault-123')
      expect(axios.get).toHaveBeenCalledWith('/api/v1/objectives/vault-123/', fetchParams)
      expect(objectivesStore.objectives).toEqual(
        mockObjectives.map((entry) => ({ ...entry, vault_id: 'vault-123' }))
      )
    })

    it('should fetch objectives with custom skip and limit', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [objective()] })
      await objectivesStore.fetchObjectives('vault-123', 10, 50)
      expect(axios.get).toHaveBeenCalledWith('/api/v1/objectives/vault-123/', {
        params: { skip: 10, limit: 50 },
      })
    })

    it('should fetch empty objectives array', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })
      await objectivesStore.fetchObjectives('vault-123')
      expect(objectivesStore.objectives).toEqual([])
    })

    it('should throw error on fetch failure', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))
      await expect(objectivesStore.fetchObjectives('vault-123')).rejects.toThrow('Network error')
    })
  })

  describe('addObjective Action', () => {
    const newObjective = { challenge: 'New challenge', total: 10, reward: '50 caps' }

    it('should add objective and refresh list', async () => {
      const updatedObjectives = [{ id: '1', ...newObjective, progress: 0, is_completed: false }]
      vi.mocked(axios.post).mockResolvedValueOnce({ data: {} })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: updatedObjectives })

      await objectivesStore.addObjective('vault-123', newObjective)
      expect(axios.post).toHaveBeenCalledWith('/api/v1/objectives/vault-123/', newObjective)
      expect(axios.get).toHaveBeenCalledWith('/api/v1/objectives/vault-123/', fetchParams)
      expect(objectivesStore.objectives).toEqual(
        updatedObjectives.map((entry) => ({ ...entry, vault_id: 'vault-123' }))
      )
    })

    it('should throw error on add failure', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Add failed'))
      await expect(objectivesStore.addObjective('vault-123', newObjective)).rejects.toThrow(
        'Add failed'
      )
    })
  })

  describe('getObjective Action', () => {
    it('should fetch single objective by ID', async () => {
      const mockObjective = objective({ id: 'obj-1', challenge: 'Complete tutorial', progress: 5 })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockObjective })
      const result = await objectivesStore.getObjective('vault-123', 'obj-1')
      expect(axios.get).toHaveBeenCalledWith('/api/v1/objectives/vault-123/obj-1')
      expect(result).toEqual(mockObjective)
    })

    it('should throw error on get failure', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Not found'))
      await expect(objectivesStore.getObjective('vault-123', 'obj-1')).rejects.toThrow('Not found')
    })
  })

  describe('Integration Scenarios', () => {
    it('keeps the current vault context when an earlier vault response arrives late', async () => {
      let resolveEarlier!: (response: unknown) => void
      vi.mocked(axios.get)
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveEarlier = resolve
            })
        )
        .mockResolvedValueOnce({ data: [{ id: 'current-objective' }] })

      const earlier = objectivesStore.fetchObjectives('earlier-vault')
      await objectivesStore.fetchObjectives('current-vault')
      resolveEarlier({ data: [{ id: 'earlier-objective' }] })
      await earlier
      expect(objectivesStore.objectivesVaultId).toBe('current-vault')
      expect(objectivesStore.objectives).toEqual([
        { id: 'current-objective', vault_id: 'current-vault' },
      ])
    })

    it('should handle complete objective workflow', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })
      await objectivesStore.fetchObjectives('vault-123')
      expect(objectivesStore.objectives).toEqual([])

      const newObjective = { challenge: 'Test', total: 10, reward: '10 caps' }
      vi.mocked(axios.post).mockResolvedValueOnce({ data: {} })
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [{ id: '1', ...newObjective, progress: 0, is_completed: false }],
      })
      await objectivesStore.addObjective('vault-123', newObjective)
      expect(objectivesStore.objectives).toHaveLength(1)
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: { id: '1', ...newObjective, progress: 5, is_completed: false },
      })
      const fetched = await objectivesStore.getObjective('vault-123', '1')
      expect(fetched.progress).toBe(5)
    })

    it('should handle multiple vaults independently', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [{ id: '1', challenge: 'Vault 1 objective' }],
      })
      await objectivesStore.fetchObjectives('vault-1')
      const vault1Objectives = [...objectivesStore.objectives]

      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [{ id: '2', challenge: 'Vault 2 objective' }],
      })
      await objectivesStore.fetchObjectives('vault-2')
      expect(objectivesStore.objectives[0].id).toBe('2')
      expect(objectivesStore.objectives).not.toEqual(vault1Objectives)
    })
  })

  describe('Data Validation', () => {
    it('should handle objectives with all fields', async () => {
      const completeObjective = {
        ...objective({
          challenge: 'Complete challenge',
          description: 'Test description',
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-02T00:00:00Z',
        }),
      }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [completeObjective] })

      await objectivesStore.fetchObjectives('vault-123')
      expect(objectivesStore.objectives[0]).toEqual({
        ...completeObjective,
        vault_id: 'vault-123',
      })
    })

    it('should handle completed objectives', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [objective({ progress: 10, total: 10, is_completed: true })],
      })
      await objectivesStore.fetchObjectives('vault-123')
      expect(objectivesStore.objectives[0].is_completed).toBe(true)
    })
  })
})

describe('Objective claim continuity', () => {
  const template = objective({ id: 'step', challenge: 'Train a stat', progress: 1, total: 1 })

  it('preserves template guidance when the claim response contains only progress state', async () => {
    setActivePinia(createPinia())
    const store = useObjectivesStore()
    store.objectivesVaultId = 'v1'
    store.objectives = [
      { ...template, reward: '200 caps', category: 'starter', sequence: 9 } as never,
    ]
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: { objective_id: 'step', progress: 1, total: 1, is_completed: true },
    })

    const result = await store.completeObjective('v1', 'step')
    expect(axios.post).toHaveBeenCalledWith('/api/v1/objectives/v1/step/claim')
    expect(result).toMatchObject({
      id: 'step',
      challenge: 'Train a stat',
      sequence: 9,
      is_completed: true,
    })
  })

  it('a late claim result cannot mark the same template claimed in a different vault', async () => {
    setActivePinia(createPinia())
    const store = useObjectivesStore()
    store.objectivesVaultId = 'v1'
    store.objectives = [{ ...template }]
    let resolve!: (value: unknown) => void
    vi.mocked(axios.post).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        }) as never
    )

    const claiming = store.completeObjective('v1', 'step')
    store.objectivesVaultId = 'v2'
    store.objectives = [{ ...template }]
    resolve({ data: { progress: 1, total: 1, is_completed: true } })
    await claiming
    expect(store.objectives[0].is_completed).toBe(false)
  })
})
