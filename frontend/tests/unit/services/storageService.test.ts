import { describe, it, expect, beforeEach, vi } from 'vitest'
import * as http from '@/core/plugins/httpClient'

vi.mock('@/core/plugins/httpClient')

import { storageService } from '@/modules/storage/services/storageService'

describe('storageService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getStorageSpace', () => {
    it('should fetch storage space from correct endpoint', async () => {
      const mockSpace = { total_space: 100, used_space: 30, free_space: 70 }
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockSpace)

      const result = await storageService.getStorageSpace('vault-1')

      expect(http.apiGet).toHaveBeenCalledWith('/api/v1/storage/vault/vault-1/space')
      expect(result).toEqual(mockSpace)
    })
  })

  describe('getStorageItems', () => {
    it('should fetch storage items', async () => {
      const mockItems = {
        weapons: [{ id: 'w1', name: 'Pistol', damage: 10 }],
        outfits: [{ id: 'o1', name: 'Armor', defense: 5 }],
        junk: [{ id: 'j1', name: 'Scrap Metal', value: 3 }],
      }
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockItems)

      const result = await storageService.getStorageItems('vault-1')

      expect(http.apiGet).toHaveBeenCalledWith('/api/v1/storage/vault/vault-1/items')
      expect(result).toEqual(mockItems)
    })
  })

  describe('sellWeapon', () => {
    it('should POST to sell weapon endpoint', async () => {
      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      await storageService.sellWeapon('w1')

      expect(http.apiPost).toHaveBeenCalledWith('/api/v1/weapons/w1/sell/')
    })
  })

  describe('sellOutfit', () => {
    it('should POST to sell outfit endpoint', async () => {
      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      await storageService.sellOutfit('o1')

      expect(http.apiPost).toHaveBeenCalledWith('/api/v1/outfits/o1/sell/')
    })
  })

  describe('sellJunk', () => {
    it('should POST to sell junk endpoint', async () => {
      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      await storageService.sellJunk('j1')

      expect(http.apiPost).toHaveBeenCalledWith('/api/v1/junk/j1/sell/')
    })
  })

  describe('scrapWeapon', () => {
    it('should POST to scrap weapon endpoint', async () => {
      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      await storageService.scrapWeapon('w1')

      expect(http.apiPost).toHaveBeenCalledWith('/api/v1/weapons/w1/scrap/')
    })
  })

  describe('scrapOutfit', () => {
    it('should POST to scrap outfit endpoint', async () => {
      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      await storageService.scrapOutfit('o1')

      expect(http.apiPost).toHaveBeenCalledWith('/api/v1/outfits/o1/scrap/')
    })
  })
})
