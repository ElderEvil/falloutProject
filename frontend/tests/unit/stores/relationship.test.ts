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

const rel = (overrides: Record<string, unknown> = {}) => ({ ...mockRelationship, ...overrides })

const seeded = (...rows: unknown[]) => {
  const store = useRelationshipStore()
  store.relationships = rows as never
  return store
}

function deferred<T = unknown>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe('Relationship Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

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
        rel({ bond_change_per_tick: 3, bond_tick_seconds: 60 }),
      ])

      const store = useRelationshipStore()
      const refresh = store.fetchVaultRelationships('vault-1', { silent: true })
      expect(store.isLoading).toBe(false)
      await refresh
      expect(store.relationships[0].bond_change_per_tick).toBe(3)
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
      const pendingFetch = deferred<unknown>()
      vi.mocked(relationshipApi.getByVault).mockReturnValueOnce(pendingFetch.promise as never)
      const romantic = rel({ relationship_type: 'romantic' })
      vi.mocked(relationshipApi.initiateRomance).mockResolvedValueOnce(romantic as never)

      const store = seeded(mockRelationship)
      const inFlight = store.fetchVaultRelationships('vault-1', { silent: true })
      await store.initiateRomance('rel-1')
      pendingFetch.resolve([mockRelationship])
      await inFlight
      expect(store.relationships[0].relationship_type).toBe('romantic')
      vi.mocked(relationshipApi.getByVault).mockResolvedValueOnce([romantic])
      await store.fetchVaultRelationships('vault-1', { silent: true })
      expect(store.relationships[0]).toEqual(romantic)
    })
  })

  describe('createRelationship', () => {
    const request = { dweller_1_id: 'dweller-1', dweller_2_id: 'dweller-2' }

    it('should create relationship successfully', async () => {
      vi.mocked(relationshipApi.create).mockResolvedValueOnce(mockRelationship)

      const store = useRelationshipStore()
      const result = await store.createRelationship(request)
      expect(relationshipApi.create).toHaveBeenCalledWith(request)
      expect(result).toEqual(mockRelationship)
      expect(store.relationships).toContainEqual(mockRelationship)
    })

    it('should handle create error', async () => {
      vi.mocked(relationshipApi.create).mockRejectedValueOnce(new Error('Failed'))
      const store = useRelationshipStore()
      expect(await store.createRelationship(request)).toBeNull()
    })
  })

  describe('initiateRomance', () => {
    it('should initiate romance successfully and keep bond progress', async () => {
      const romanticRelationship = rel({ relationship_type: 'romantic' })
      vi.mocked(relationshipApi.initiateRomance).mockResolvedValueOnce(
        romanticRelationship as never
      )

      const store = seeded(rel({ bond_change_per_tick: 3, bond_tick_seconds: 60 }))
      const result = await store.initiateRomance('rel-1')
      expect(relationshipApi.initiateRomance).toHaveBeenCalledWith('rel-1')
      expect(result?.relationship_type).toBe('romantic')
      expect(store.relationships[0].relationship_type).toBe('romantic')
      expect(store.relationships[0].bond_change_per_tick).toBe(3)
    })

    it('should handle romance error', async () => {
      vi.mocked(relationshipApi.initiateRomance).mockRejectedValueOnce({
        response: { data: { detail: 'Affinity too low' } },
      })
      const store = useRelationshipStore()
      expect(await store.initiateRomance('rel-1')).toBeNull()
    })
  })

  describe('makePartners', () => {
    it('should make partners successfully', async () => {
      const partnerRelationship = rel({ relationship_type: 'partner' })
      vi.mocked(relationshipApi.makePartners).mockResolvedValueOnce(partnerRelationship as never)

      const store = seeded(rel({ relationship_type: 'romantic' }))
      const result = await store.makePartners('rel-1')
      expect(relationshipApi.makePartners).toHaveBeenCalledWith('rel-1')
      expect(result?.relationship_type).toBe('partner')
      expect(store.relationships[0].relationship_type).toBe('partner')
    })
  })

  describe('breakUp', () => {
    it('should break up relationship successfully', async () => {
      vi.mocked(relationshipApi.breakUp).mockResolvedValueOnce({ message: 'Relationship ended' })

      const store = seeded(mockRelationship)
      const result = await store.breakUp('rel-1')
      expect(relationshipApi.breakUp).toHaveBeenCalledWith('rel-1')
      expect(result).toBe(true)
      expect(store.relationships[0].relationship_type).toBe('ex')
      expect(store.relationships[0].affinity).toBeLessThan(50)
    })

    it('should handle breakup error', async () => {
      vi.mocked(relationshipApi.breakUp).mockRejectedValueOnce(new Error('Failed'))
      const store = useRelationshipStore()
      expect(await store.breakUp('rel-1')).toBe(false)
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
      expect(await store.calculateCompatibility('dweller-1', 'dweller-2')).toBeNull()
    })
  })

  describe('Computed Properties', () => {
    it('should get relationship by dwellers in either order', () => {
      const store = seeded(mockRelationship)
      expect(store.getRelationshipByDwellers('dweller-1', 'dweller-2')).toEqual(mockRelationship)
      expect(store.getRelationshipByDwellers('dweller-2', 'dweller-1')).toEqual(mockRelationship)
    })

    it('should get partner and romantic relationships separately', () => {
      const store = seeded(
        mockRelationship,
        rel({ id: 'rel-2', relationship_type: 'partner' }),
        rel({ id: 'rel-3', relationship_type: 'romantic' })
      )

      expect(store.getPartnerRelationships.map((row) => row.relationship_type)).toEqual(['partner'])
      expect(store.getRomanticRelationships.map((row) => row.relationship_type)).toEqual([
        'romantic',
      ])
    })
  })

  describe('clearRelationships', () => {
    it('should clear all relationships', () => {
      const store = seeded(mockRelationship)
      store.clearRelationships()
      expect(store.relationships).toEqual([])
    })
  })
})
