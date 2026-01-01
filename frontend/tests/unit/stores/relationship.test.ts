import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRelationshipStore } from '@/stores/relationship'
import axios from '@/plugins/axios'

vi.mock('@/plugins/axios')

describe('Relationship Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mockRelationship = {
    id: 'rel-1',
    dweller_1_id: 'dweller-1',
    dweller_2_id: 'dweller-2',
    relationship_type: 'acquaintance',
    affinity: 50,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z'
  }

  const mockCompatibilityScore = {
    dweller_1_id: 'dweller-1',
    dweller_2_id: 'dweller-2',
    score: 0.75,
    special_score: 0.8,
    happiness_score: 0.9,
    level_score: 0.7,
    proximity_score: 0.0
  }

  describe('State Initialization', () => {
    it('should initialize with empty relationships', () => {
      const store = useRelationshipStore()
      expect(store.relationships).toEqual([])
      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchVaultRelationships', () => {
    it('should fetch relationships successfully', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [mockRelationship] })

      const store = useRelationshipStore()
      await store.fetchVaultRelationships('vault-1')

      expect(axios.get).toHaveBeenCalledWith('/api/v1/relationships/vault/vault-1')
      expect(store.relationships).toEqual([mockRelationship])
      expect(store.isLoading).toBe(false)
    })

    it('should handle fetch error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      const store = useRelationshipStore()
      await store.fetchVaultRelationships('vault-1')

      expect(store.relationships).toEqual([])
      expect(store.isLoading).toBe(false)
    })
  })

  describe('createRelationship', () => {
    it('should create relationship successfully', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: mockRelationship })

      const store = useRelationshipStore()
      const result = await store.createRelationship({
        dweller_1_id: 'dweller-1',
        dweller_2_id: 'dweller-2'
      })

      expect(axios.post).toHaveBeenCalledWith('/api/v1/relationships/', {
        dweller_1_id: 'dweller-1',
        dweller_2_id: 'dweller-2'
      })
      expect(result).toEqual(mockRelationship)
      expect(store.relationships).toContainEqual(mockRelationship)
    })

    it('should handle create error', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Failed'))

      const store = useRelationshipStore()
      const result = await store.createRelationship({
        dweller_1_id: 'dweller-1',
        dweller_2_id: 'dweller-2'
      })

      expect(result).toBeNull()
    })
  })

  describe('initiateRomance', () => {
    it('should initiate romance successfully', async () => {
      const romanticRelationship = { ...mockRelationship, relationship_type: 'romantic' }
      vi.mocked(axios.put).mockResolvedValueOnce({ data: romanticRelationship })

      const store = useRelationshipStore()
      store.relationships = [mockRelationship]

      const result = await store.initiateRomance('rel-1')

      expect(axios.put).toHaveBeenCalledWith('/api/v1/relationships/rel-1/romance')
      expect(result?.relationship_type).toBe('romantic')
      expect(store.relationships[0].relationship_type).toBe('romantic')
    })

    it('should handle romance error', async () => {
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Affinity too low' } }
      })

      const store = useRelationshipStore()
      const result = await store.initiateRomance('rel-1')

      expect(result).toBeNull()
    })
  })

  describe('makePartners', () => {
    it('should make partners successfully', async () => {
      const partnerRelationship = { ...mockRelationship, relationship_type: 'partner' }
      vi.mocked(axios.put).mockResolvedValueOnce({ data: partnerRelationship })

      const store = useRelationshipStore()
      store.relationships = [{ ...mockRelationship, relationship_type: 'romantic' }]

      const result = await store.makePartners('rel-1')

      expect(axios.put).toHaveBeenCalledWith('/api/v1/relationships/rel-1/partner')
      expect(result?.relationship_type).toBe('partner')
      expect(store.relationships[0].relationship_type).toBe('partner')
    })
  })

  describe('breakUp', () => {
    it('should break up relationship successfully', async () => {
      vi.mocked(axios.delete).mockResolvedValueOnce({
        data: { message: 'Relationship ended' }
      })

      const store = useRelationshipStore()
      store.relationships = [mockRelationship]

      const result = await store.breakUp('rel-1')

      expect(axios.delete).toHaveBeenCalledWith('/api/v1/relationships/rel-1')
      expect(result).toBe(true)
      expect(store.relationships[0].relationship_type).toBe('ex')
      expect(store.relationships[0].affinity).toBeLessThan(50)
    })

    it('should handle breakup error', async () => {
      vi.mocked(axios.delete).mockRejectedValueOnce(new Error('Failed'))

      const store = useRelationshipStore()
      const result = await store.breakUp('rel-1')

      expect(result).toBe(false)
    })
  })

  describe('calculateCompatibility', () => {
    it('should calculate compatibility successfully', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockCompatibilityScore })

      const store = useRelationshipStore()
      const result = await store.calculateCompatibility('dweller-1', 'dweller-2')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/relationships/compatibility/dweller-1/dweller-2'
      )
      expect(result).toEqual(mockCompatibilityScore)
    })

    it('should handle compatibility error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Failed'))

      const store = useRelationshipStore()
      const result = await store.calculateCompatibility('dweller-1', 'dweller-2')

      expect(result).toBeNull()
    })
  })

  describe('quickPair', () => {
    it('should quick pair dwellers successfully', async () => {
      const partnerRelationship = { ...mockRelationship, relationship_type: 'partner', affinity: 90 }
      vi.mocked(axios.post).mockResolvedValueOnce({ data: partnerRelationship })

      const store = useRelationshipStore()
      const result = await store.quickPair('vault-1')

      expect(axios.post).toHaveBeenCalledWith('/api/v1/relationships/vault/vault-1/quick-pair')
      expect(result).toEqual(partnerRelationship)
      expect(store.relationships).toContainEqual(partnerRelationship)
    })

    it('should handle quick pair error with insufficient dwellers', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce({
        response: { data: { detail: 'Need at least 2 adult dwellers without partners' } }
      })

      const store = useRelationshipStore()
      const result = await store.quickPair('vault-1')

      expect(result).toBeNull()
    })
  })

  describe('Computed Properties', () => {
    it('should get relationship by dwellers', () => {
      const store = useRelationshipStore()
      store.relationships = [mockRelationship]

      const found = store.getRelationshipByDwellers('dweller-1', 'dweller-2')
      expect(found).toEqual(mockRelationship)

      // Should work in reverse order too
      const foundReverse = store.getRelationshipByDwellers('dweller-2', 'dweller-1')
      expect(foundReverse).toEqual(mockRelationship)
    })

    it('should get partner relationships', () => {
      const store = useRelationshipStore()
      store.relationships = [
        mockRelationship,
        { ...mockRelationship, id: 'rel-2', relationship_type: 'partner' },
        { ...mockRelationship, id: 'rel-3', relationship_type: 'romantic' }
      ]

      const partners = store.getPartnerRelationships
      expect(partners).toHaveLength(1)
      expect(partners[0].relationship_type).toBe('partner')
    })

    it('should get romantic relationships', () => {
      const store = useRelationshipStore()
      store.relationships = [
        mockRelationship,
        { ...mockRelationship, id: 'rel-2', relationship_type: 'romantic' },
        { ...mockRelationship, id: 'rel-3', relationship_type: 'partner' }
      ]

      const romantics = store.getRomanticRelationships
      expect(romantics).toHaveLength(1)
      expect(romantics[0].relationship_type).toBe('romantic')
    })
  })

  describe('clearRelationships', () => {
    it('should clear all relationships', () => {
      const store = useRelationshipStore()
      store.relationships = [mockRelationship]

      store.clearRelationships()
      expect(store.relationships).toEqual([])
    })
  })
})
