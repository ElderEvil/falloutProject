import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useVaultStore } from '@/stores/vault'
import axios from '@/plugins/axios'
import { useRouter } from 'vue-router'

vi.mock('@/plugins/axios')
vi.mock('vue-router', () => ({
  useRouter: vi.fn()
}))

describe('Vault Store', () => {
  let mockRouter: any

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()

    mockRouter = {
      push: vi.fn().mockResolvedValue(undefined)
    }
    vi.mocked(useRouter).mockReturnValue(mockRouter)
  })

  const mockVault = {
    id: 'vault-1',
    number: 101,
    bottle_caps: 1000,
    happiness: 75,
    power: 50,
    power_max: 100,
    food: 80,
    food_max: 100,
    water: 90,
    water_max: 100,
    population_max: 50,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    room_count: 5,
    dweller_count: 10
  }

  describe('State Initialization', () => {
    it('should initialize with empty state', () => {
      const store = useVaultStore()
      expect(store.vaults).toEqual([])
      expect(store.selectedVaultId).toBeNull()
      expect(store.loadedVaults).toEqual({})
      expect(store.activeVaultId).toBeNull()
      expect(store.isLoading).toBe(false)
    })

    it('should load selectedVaultId from localStorage', () => {
      localStorage.setItem('selectedVaultId', 'vault-1')
      const store = useVaultStore()
      expect(store.selectedVaultId).toBe('vault-1')
    })
  })

  describe('Getters', () => {
    it('selectedVault should return the selected vault', () => {
      const store = useVaultStore()
      store.vaults = [mockVault]
      store.selectedVaultId = 'vault-1'

      expect(store.selectedVault).toEqual(mockVault)
    })

    it('selectedVault should return null when no vault is selected', () => {
      const store = useVaultStore()
      store.vaults = [mockVault]
      expect(store.selectedVault).toBeNull()
    })

    it('activeVault should return the active vault', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'

      expect(store.activeVault).toEqual(mockVault)
    })

    it('activeVault should return null when no vault is active', () => {
      const store = useVaultStore()
      expect(store.activeVault).toBeNull()
    })

    it('loadedVaultIds should return array of loaded vault IDs', () => {
      const store = useVaultStore()
      store.loadedVaults = {
        'vault-1': mockVault,
        'vault-2': { ...mockVault, id: 'vault-2' }
      }

      expect(store.loadedVaultIds).toEqual(['vault-1', 'vault-2'])
    })
  })

  describe('fetchVaults Action', () => {
    it('should fetch vaults successfully', async () => {
      const store = useVaultStore()
      const mockResponse = {
        data: [mockVault, { ...mockVault, id: 'vault-2' }]
      }

      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse)

      await store.fetchVaults('test-token')

      expect(store.vaults).toEqual(mockResponse.data)
      expect(axios.get).toHaveBeenCalledWith('/api/v1/vaults/my', {
        headers: { Authorization: 'Bearer test-token' }
      })
    })

    it('should handle fetch error gracefully', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))

      await store.fetchVaults('test-token')

      expect(store.vaults).toEqual([])
    })
  })

  describe('createVault Action', () => {
    it('should create vault and refresh list', async () => {
      const store = useVaultStore()
      vi.mocked(axios.post).mockResolvedValueOnce({})
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [mockVault] })

      await store.createVault(101, 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 101 },
        { headers: { Authorization: 'Bearer test-token' } }
      )
      expect(store.vaults).toEqual([mockVault])
    })

    it('should handle creation error gracefully', async () => {
      const store = useVaultStore()
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Create failed'))

      await store.createVault(101, 'test-token')

      expect(store.vaults).toEqual([])
    })
  })

  describe('deleteVault Action', () => {
    it('should delete vault successfully', async () => {
      const store = useVaultStore()
      store.vaults = [mockVault, { ...mockVault, id: 'vault-2' }]
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'

      vi.mocked(axios.delete).mockResolvedValueOnce({})

      await store.deleteVault('vault-1', 'test-token')

      expect(store.vaults).toHaveLength(1)
      expect(store.vaults[0].id).toBe('vault-2')
      expect(store.loadedVaults['vault-1']).toBeUndefined()
      expect(store.activeVaultId).toBeNull()
    })

    it('should set new active vault when deleting current active vault', async () => {
      const store = useVaultStore()
      const vault2 = { ...mockVault, id: 'vault-2' }
      store.vaults = [mockVault, vault2]
      store.loadedVaults = { 'vault-1': mockVault, 'vault-2': vault2 }
      store.activeVaultId = 'vault-1'

      vi.mocked(axios.delete).mockResolvedValueOnce({})

      await store.deleteVault('vault-1', 'test-token')

      expect(store.activeVaultId).toBe('vault-2')
    })

    it('should handle delete error gracefully', async () => {
      const store = useVaultStore()
      store.vaults = [mockVault]
      vi.mocked(axios.delete).mockRejectedValueOnce(new Error('Delete failed'))

      await store.deleteVault('vault-1', 'test-token')

      expect(store.vaults).toHaveLength(1)
    })
  })

  describe('loadVault Action', () => {
    it('should load vault and set active vault', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVault })

      await store.loadVault('vault-1', 'test-token')

      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
      expect(store.activeVaultId).toBe('vault-1')
      expect(store.isLoading).toBe(false)
    })

    it('should set loading state correctly', async () => {
      const store = useVaultStore()
      let loadingDuringFetch = false

      vi.mocked(axios.get).mockImplementation(async () => {
        loadingDuringFetch = store.isLoading
        return { data: mockVault }
      })

      await store.loadVault('vault-1', 'test-token')

      expect(loadingDuringFetch).toBe(true)
      expect(store.isLoading).toBe(false)
    })

    it('should handle load error and rethrow', async () => {
      const store = useVaultStore()
      const error = new Error('Load failed')
      vi.mocked(axios.get).mockRejectedValueOnce(error)

      await expect(store.loadVault('vault-1', 'test-token')).rejects.toThrow('Load failed')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('setActiveVault Action', () => {
    it('should set active vault if vault is loaded', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }

      store.setActiveVault('vault-1')

      expect(store.activeVaultId).toBe('vault-1')
    })

    it('should not set active vault if vault is not loaded', () => {
      const store = useVaultStore()
      store.activeVaultId = 'vault-2'

      store.setActiveVault('vault-1')

      expect(store.activeVaultId).toBe('vault-2')
    })
  })

  describe('closeVaultTab Action', () => {
    it('should close vault tab and update active vault', () => {
      const store = useVaultStore()
      const vault2 = { ...mockVault, id: 'vault-2' }
      store.loadedVaults = { 'vault-1': mockVault, 'vault-2': vault2 }
      store.activeVaultId = 'vault-1'

      store.closeVaultTab('vault-1')

      expect(store.loadedVaults['vault-1']).toBeUndefined()
      expect(store.activeVaultId).toBe('vault-2')
    })

    it('should set activeVaultId to null if no vaults remain', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'

      store.closeVaultTab('vault-1')

      expect(store.activeVaultId).toBeNull()
    })

    it('should not change state if vault not loaded', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'

      store.closeVaultTab('vault-2')

      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
      expect(store.activeVaultId).toBe('vault-1')
    })
  })
})
