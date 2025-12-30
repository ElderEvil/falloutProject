import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useObjectivesStore } from '@/stores/objectives'
import axios from '@/plugins/axios'

vi.mock('@/plugins/axios')

describe('Objectives Store', () => {
  let objectivesStore: ReturnType<typeof useObjectivesStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    objectivesStore = useObjectivesStore()
    vi.clearAllMocks()
  })

  describe('State', () => {
    it('should initialize with empty objectives array', () => {
      expect(objectivesStore.objectives).toEqual([])
    })
  })

  describe('fetchObjectives Action', () => {
    describe('Happy Path', () => {
      it('should fetch objectives successfully', async () => {
        const mockObjectives = [
          {
            id: '1',
            challenge: 'Collect 100 caps',
            progress: 50,
            total: 100,
            reward: '50 caps',
            is_completed: false
          },
          {
            id: '2',
            challenge: 'Build 5 rooms',
            progress: 3,
            total: 5,
            reward: '100 caps',
            is_completed: false
          }
        ]

        vi.mocked(axios.get).mockResolvedValueOnce({ data: mockObjectives })

        await objectivesStore.fetchObjectives('vault-123')

        expect(axios.get).toHaveBeenCalledWith('/api/v1/objectives/vault-123/', {
          params: { skip: 0, limit: 100 }
        })
        expect(objectivesStore.objectives).toEqual(mockObjectives)
      })

      it('should fetch objectives with custom skip and limit', async () => {
        const mockObjectives = [{ id: '1', challenge: 'Test' }]
        vi.mocked(axios.get).mockResolvedValueOnce({ data: mockObjectives })

        await objectivesStore.fetchObjectives('vault-123', 10, 50)

        expect(axios.get).toHaveBeenCalledWith('/api/v1/objectives/vault-123/', {
          params: { skip: 10, limit: 50 }
        })
      })

      it('should use correct API endpoint format (bug fix validation)', async () => {
        // This test validates our fix: changed from /api/v1/${vaultId}/ to /api/v1/objectives/${vaultId}/
        vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

        await objectivesStore.fetchObjectives('abc-123')

        const calledUrl = vi.mocked(axios.get).mock.calls[0][0]
        expect(calledUrl).toBe('/api/v1/objectives/abc-123/')
        expect(calledUrl).toContain('/objectives/')
        expect(calledUrl).not.toBe('/api/v1/abc-123/') // Old incorrect format
      })

      it('should fetch empty objectives array', async () => {
        vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

        await objectivesStore.fetchObjectives('vault-123')

        expect(objectivesStore.objectives).toEqual([])
      })
    })

    describe('Error Handling', () => {
      it('should throw error on fetch failure', async () => {
        const error = new Error('Network error')
        vi.mocked(axios.get).mockRejectedValueOnce(error)

        await expect(objectivesStore.fetchObjectives('vault-123')).rejects.toThrow('Network error')
      })

      it('should log error to console on fetch failure', async () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
        const error = new Error('Fetch failed')
        vi.mocked(axios.get).mockRejectedValueOnce(error)

        try {
          await objectivesStore.fetchObjectives('vault-123')
        } catch (e) {
          // Expected to throw
        }

        expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch objectives:', error)
        consoleSpy.mockRestore()
      })
    })
  })

  describe('addObjective Action', () => {
    describe('Happy Path', () => {
      it('should add objective and refresh list', async () => {
        const newObjective = {
          challenge: 'New challenge',
          total: 10,
          reward: '50 caps'
        }
        const updatedObjectives = [
          { id: '1', ...newObjective, progress: 0, is_completed: false }
        ]

        vi.mocked(axios.post).mockResolvedValueOnce({ data: {} })
        vi.mocked(axios.get).mockResolvedValueOnce({ data: updatedObjectives })

        await objectivesStore.addObjective('vault-123', newObjective)

        expect(axios.post).toHaveBeenCalledWith('/api/v1/objectives/vault-123/', newObjective)
        expect(axios.get).toHaveBeenCalledWith('/api/v1/objectives/vault-123/', {
          params: { skip: 0, limit: 100 }
        })
        expect(objectivesStore.objectives).toEqual(updatedObjectives)
      })

      it('should use correct API endpoint format for add (bug fix validation)', async () => {
        vi.mocked(axios.post).mockResolvedValueOnce({ data: {} })
        vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

        await objectivesStore.addObjective('vault-456', { challenge: 'Test' })

        const calledUrl = vi.mocked(axios.post).mock.calls[0][0]
        expect(calledUrl).toBe('/api/v1/objectives/vault-456/')
        expect(calledUrl).toContain('/objectives/')
        expect(calledUrl).not.toBe('/api/v1/vault-456/') // Old incorrect format
      })
    })

    describe('Error Handling', () => {
      it('should throw error on add failure', async () => {
        const error = new Error('Add failed')
        vi.mocked(axios.post).mockRejectedValueOnce(error)

        await expect(
          objectivesStore.addObjective('vault-123', { challenge: 'Test' })
        ).rejects.toThrow('Add failed')
      })

      it('should log error to console on add failure', async () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
        const error = new Error('Post failed')
        vi.mocked(axios.post).mockRejectedValueOnce(error)

        try {
          await objectivesStore.addObjective('vault-123', { challenge: 'Test' })
        } catch (e) {
          // Expected to throw
        }

        expect(consoleSpy).toHaveBeenCalledWith('Failed to add objective:', error)
        consoleSpy.mockRestore()
      })
    })
  })

  describe('getObjective Action', () => {
    describe('Happy Path', () => {
      it('should fetch single objective by ID', async () => {
        const mockObjective = {
          id: 'obj-1',
          challenge: 'Complete tutorial',
          progress: 5,
          total: 10,
          reward: '25 caps',
          is_completed: false
        }

        vi.mocked(axios.get).mockResolvedValueOnce({ data: mockObjective })

        const result = await objectivesStore.getObjective('vault-123', 'obj-1')

        expect(axios.get).toHaveBeenCalledWith('/api/v1/objectives/vault-123/obj-1')
        expect(result).toEqual(mockObjective)
      })

      it('should use correct API endpoint format for get (bug fix validation)', async () => {
        vi.mocked(axios.get).mockResolvedValueOnce({ data: {} })

        await objectivesStore.getObjective('vault-789', 'obj-xyz')

        const calledUrl = vi.mocked(axios.get).mock.calls[0][0]
        expect(calledUrl).toBe('/api/v1/objectives/vault-789/obj-xyz')
        expect(calledUrl).toContain('/objectives/')
        expect(calledUrl).not.toBe('/api/v1/vault-789/obj-xyz') // Old incorrect format
      })
    })

    describe('Error Handling', () => {
      it('should throw error on get failure', async () => {
        const error = new Error('Not found')
        vi.mocked(axios.get).mockRejectedValueOnce(error)

        await expect(
          objectivesStore.getObjective('vault-123', 'obj-1')
        ).rejects.toThrow('Not found')
      })

      it('should log error to console on get failure', async () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
        const error = new Error('Get failed')
        vi.mocked(axios.get).mockRejectedValueOnce(error)

        try {
          await objectivesStore.getObjective('vault-123', 'obj-1')
        } catch (e) {
          // Expected to throw
        }

        expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch objective:', error)
        consoleSpy.mockRestore()
      })
    })
  })

  describe('Integration Scenarios', () => {
    it('should handle complete objective workflow', async () => {
      // Initial fetch
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })
      await objectivesStore.fetchObjectives('vault-123')
      expect(objectivesStore.objectives).toEqual([])

      // Add objective
      const newObjective = { challenge: 'Test', total: 10, reward: '10 caps' }
      vi.mocked(axios.post).mockResolvedValueOnce({ data: {} })
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [{ id: '1', ...newObjective, progress: 0, is_completed: false }]
      })
      await objectivesStore.addObjective('vault-123', newObjective)
      expect(objectivesStore.objectives).toHaveLength(1)

      // Get specific objective
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: { id: '1', ...newObjective, progress: 5, is_completed: false }
      })
      const objective = await objectivesStore.getObjective('vault-123', '1')
      expect(objective.progress).toBe(5)
    })

    it('should handle multiple vaults independently', async () => {
      // Fetch for vault 1
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [{ id: '1', challenge: 'Vault 1 objective' }]
      })
      await objectivesStore.fetchObjectives('vault-1')
      const vault1Objectives = [...objectivesStore.objectives]

      // Fetch for vault 2
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [{ id: '2', challenge: 'Vault 2 objective' }]
      })
      await objectivesStore.fetchObjectives('vault-2')

      // Store should now have vault 2's objectives
      expect(objectivesStore.objectives[0].id).toBe('2')
      expect(objectivesStore.objectives).not.toEqual(vault1Objectives)
    })
  })

  describe('Data Validation', () => {
    it('should handle objectives with all fields', async () => {
      const completeObjective = {
        id: '1',
        challenge: 'Complete challenge',
        progress: 50,
        total: 100,
        reward: '100 caps',
        is_completed: false,
        description: 'Test description',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z'
      }

      vi.mocked(axios.get).mockResolvedValueOnce({ data: [completeObjective] })
      await objectivesStore.fetchObjectives('vault-123')

      expect(objectivesStore.objectives[0]).toEqual(completeObjective)
    })

    it('should handle completed objectives', async () => {
      const completedObjective = {
        id: '1',
        challenge: 'Test',
        progress: 10,
        total: 10,
        reward: '50 caps',
        is_completed: true
      }

      vi.mocked(axios.get).mockResolvedValueOnce({ data: [completedObjective] })
      await objectivesStore.fetchObjectives('vault-123')

      expect(objectivesStore.objectives[0].is_completed).toBe(true)
    })
  })
})
