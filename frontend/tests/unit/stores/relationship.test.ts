import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useRelationshipStore } from '@/modules/social/stores/relationship'
import { relationshipApi } from '@/modules/social/api/relationship'
import { handleStoreError } from '@/core/utils/errorHandler'

vi.mock('@/modules/social/api/relationship', () => ({
  relationshipApi: {
    getByVault: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    initiateRomance: vi.fn(),
    makePartners: vi.fn(),
    marry: vi.fn(),
    breakUp: vi.fn(),
    getCompatibility: vi.fn(),
    processVaultBreeding: vi.fn(),
  },
}))
vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
  handleStoreError: vi.fn(),
}))

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
    updated_at: '2026-01-01T00:00:00Z',
  }

  const mockCompatibilityScore = {
    dweller_1_id: 'dweller-1',
    dweller_2_id: 'dweller-2',
    score: 0.75,
    special_score: 0.8,
    happiness_score: 0.9,
    level_score: 0.7,
    proximity_score: 0.0,
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
      vi.mocked(relationshipApi.getByVault).mockResolvedValueOnce([mockRelationship])

      const store = useRelationshipStore()
      await store.fetchVaultRelationships('vault-1')

      expect(relationshipApi.getByVault).toHaveBeenCalledWith('vault-1')
      expect(store.relationships).toEqual([mockRelationship])
      expect(store.isLoading).toBe(false)
    })

    it('should handle fetch error', async () => {
      vi.mocked(relationshipApi.getByVault).mockRejectedValueOnce(new Error('Network error'))

      const store = useRelationshipStore()
      await expect(store.fetchVaultRelationships('vault-1')).rejects.toThrow('Network error')

      expect(store.relationships).toEqual([])
      expect(store.isLoading).toBe(false)
    })

    it('refreshes bond progress without replacing the list with a loading state', async () => {
      vi.mocked(relationshipApi.getByVault).mockResolvedValueOnce([
        { ...mockRelationship, bond_growth_per_tick: 3, bond_tick_seconds: 60 },
      ])

      const store = useRelationshipStore()
      const refresh = store.fetchVaultRelationships('vault-1', { silent: true })

      expect(store.isLoading).toBe(false)
      await refresh
      expect(store.relationships[0].bond_growth_per_tick).toBe(3)
    })

    it('rethrows silent fetch errors without showing a store notification', async () => {
      vi.mocked(relationshipApi.getByVault).mockRejectedValueOnce(new Error('Network error'))

      const store = useRelationshipStore()
      await expect(store.fetchVaultRelationships('vault-1', { silent: true })).rejects.toThrow(
        'Network error'
      )

      expect(handleStoreError).toHaveBeenCalledWith(
        expect.any(Error),
        'Failed to fetch relationships',
        false
      )
    })

    it('keeps a completed romance when an older fetch resolves later', async () => {
      let resolveFetch!: (value: (typeof mockRelationship)[]) => void
      vi.mocked(relationshipApi.getByVault).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFetch = resolve
          })
      )
      const romantic = { ...mockRelationship, relationship_type: 'romantic' }
      vi.mocked(relationshipApi.initiateRomance).mockResolvedValueOnce(romantic)

      const store = useRelationshipStore()
      store.relationships = [mockRelationship]
      const pendingFetch = store.fetchVaultRelationships('vault-1', { silent: true })
      await store.initiateRomance('rel-1')
      resolveFetch([mockRelationship])
      await pendingFetch

      expect(store.relationships[0].relationship_type).toBe('romantic')

      vi.mocked(relationshipApi.getByVault).mockResolvedValueOnce([romantic])
      await store.fetchVaultRelationships('vault-1', { silent: true })
      expect(store.relationships[0]).toEqual(romantic)
    })
  })

  describe('createRelationship', () => {
    it('should create relationship successfully', async () => {
      vi.mocked(relationshipApi.create).mockResolvedValueOnce(mockRelationship)

      const store = useRelationshipStore()
      const result = await store.createRelationship({
        dweller_1_id: 'dweller-1',
        dweller_2_id: 'dweller-2',
      })

      expect(relationshipApi.create).toHaveBeenCalledWith({
        dweller_1_id: 'dweller-1',
        dweller_2_id: 'dweller-2',
      })
      expect(result).toEqual(mockRelationship)
      expect(store.relationships).toContainEqual(mockRelationship)
    })

    it('should handle create error', async () => {
      vi.mocked(relationshipApi.create).mockRejectedValueOnce(new Error('Failed'))

      const store = useRelationshipStore()
      const result = await store.createRelationship({
        dweller_1_id: 'dweller-1',
        dweller_2_id: 'dweller-2',
      })

      expect(result).toBeNull()
    })
  })

  describe('initiateRomance', () => {
    it('should initiate romance successfully', async () => {
      const romanticRelationship = { ...mockRelationship, relationship_type: 'romantic' }
      vi.mocked(relationshipApi.initiateRomance).mockResolvedValueOnce(romanticRelationship)

      const store = useRelationshipStore()
      store.relationships = [
        { ...mockRelationship, bond_growth_per_tick: 3, bond_tick_seconds: 60 },
      ]

      const result = await store.initiateRomance('rel-1')

      expect(relationshipApi.initiateRomance).toHaveBeenCalledWith('rel-1')
      expect(result?.relationship_type).toBe('romantic')
      expect(store.relationships[0].relationship_type).toBe('romantic')
      expect(store.relationships[0].bond_growth_per_tick).toBe(3)
    })

    it('should handle romance error', async () => {
      vi.mocked(relationshipApi.initiateRomance).mockRejectedValueOnce({
        response: { data: { detail: 'Affinity too low' } },
      })

      const store = useRelationshipStore()
      const result = await store.initiateRomance('rel-1')

      expect(result).toBeNull()
    })
  })

  describe('makePartners', () => {
    it('should make partners successfully', async () => {
      const partnerRelationship = { ...mockRelationship, relationship_type: 'partner' }
      vi.mocked(relationshipApi.makePartners).mockResolvedValueOnce(partnerRelationship)

      const store = useRelationshipStore()
      store.relationships = [{ ...mockRelationship, relationship_type: 'romantic' }]

      const result = await store.makePartners('rel-1')

      expect(relationshipApi.makePartners).toHaveBeenCalledWith('rel-1')
      expect(result?.relationship_type).toBe('partner')
      expect(store.relationships[0].relationship_type).toBe('partner')
    })
  })

  describe('breakUp', () => {
    it('should break up relationship successfully', async () => {
      vi.mocked(relationshipApi.breakUp).mockResolvedValueOnce({ message: 'Relationship ended' })

      const store = useRelationshipStore()
      store.relationships = [mockRelationship]

      const result = await store.breakUp('rel-1')

      expect(relationshipApi.breakUp).toHaveBeenCalledWith('rel-1')
      expect(result).toBe(true)
      expect(store.relationships[0].relationship_type).toBe('ex')
      expect(store.relationships[0].affinity).toBeLessThan(50)
    })

    it('should handle breakup error', async () => {
      vi.mocked(relationshipApi.breakUp).mockRejectedValueOnce(new Error('Failed'))

      const store = useRelationshipStore()
      const result = await store.breakUp('rel-1')

      expect(result).toBe(false)
    })
  })

  describe('calculateCompatibility', () => {
    it('should calculate compatibility successfully', async () => {
      vi.mocked(relationshipApi.getCompatibility).mockResolvedValueOnce(mockCompatibilityScore)

      const store = useRelationshipStore()
      const result = await store.calculateCompatibility('dweller-1', 'dweller-2')

      expect(relationshipApi.getCompatibility).toHaveBeenCalledWith('dweller-1', 'dweller-2')
      expect(result).toEqual(mockCompatibilityScore)
    })

    it('should handle compatibility error', async () => {
      vi.mocked(relationshipApi.getCompatibility).mockRejectedValueOnce(new Error('Failed'))

      const store = useRelationshipStore()
      const result = await store.calculateCompatibility('dweller-1', 'dweller-2')

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
        { ...mockRelationship, id: 'rel-3', relationship_type: 'romantic' },
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
        { ...mockRelationship, id: 'rel-3', relationship_type: 'partner' },
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
