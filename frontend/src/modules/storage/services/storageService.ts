import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

type StorageSpaceResponse = components['schemas']['StorageSpaceResponse']
type WeaponRead = components['schemas']['WeaponRead']
type OutfitRead = components['schemas']['OutfitRead']
type JunkRead = components['schemas']['JunkRead']

export interface StorageItemsResponse {
  weapons: WeaponRead[]
  outfits: OutfitRead[]
  junk: JunkRead[]
}

export const storageService = {
  /**
   * Get storage space information for a vault
   */
  async getStorageSpace(vaultId: string): Promise<StorageSpaceResponse> {
    const response = await axios.get<StorageSpaceResponse>(`/api/v1/storage/vault/${vaultId}/space`)
    return response.data
  },

  /**
   * Get all items stored in vault storage
   */
  async getStorageItems(vaultId: string): Promise<StorageItemsResponse> {
    const response = await axios.get<StorageItemsResponse>(`/api/v1/storage/vault/${vaultId}/items`)
    return response.data
  },

  /**
   * Sell a weapon from storage
   */
  async sellWeapon(weaponId: string): Promise<void> {
    await axios.post(`/api/v1/weapons/${weaponId}/sell/`)
  },

  /**
   * Sell an outfit from storage
   */
  async sellOutfit(outfitId: string): Promise<void> {
    await axios.post(`/api/v1/outfits/${outfitId}/sell/`)
  },

  /**
   * Sell a junk item from storage
   */
  async sellJunk(junkId: string): Promise<void> {
    await axios.post(`/api/v1/junk/${junkId}/sell/`)
  },

  /**
   * Scrap a weapon from storage
   */
  async scrapWeapon(weaponId: string): Promise<void> {
    await axios.post(`/api/v1/weapons/${weaponId}/scrap/`)
  },

  /**
   * Scrap an outfit from storage
   */
  async scrapOutfit(outfitId: string): Promise<void> {
    await axios.post(`/api/v1/outfits/${outfitId}/scrap/`)
  },
}
