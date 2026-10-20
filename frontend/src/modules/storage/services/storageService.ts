import axios from '@/core/plugins/axios'
import { apiGet, type ApiRequestOptions } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

type StorageSpaceResponse = components['schemas']['StorageSpaceResponse']
type WeaponRead = components['schemas']['WeaponRead']
type OutfitRead = components['schemas']['OutfitRead']
type JunkRead = components['schemas']['JunkRead']
type ItemRead = components['schemas']['ItemRead']
type PetRead = components['schemas']['PetRead']
type LunchboxOpened = components['schemas']['LunchboxOpened']
type LunchboxOpenRequest = components['schemas']['LunchboxOpenRequest']

export interface StorageItemsResponse {
  weapons: WeaponRead[]
  outfits: OutfitRead[]
  junk: JunkRead[]
  items: ItemRead[]
  pets: PetRead[]
}

export type StorageMaintenance = components['schemas']['StorageMaintenanceRead']

export const storageService = {
  async getMaintenance(vaultId: string): Promise<StorageMaintenance> {
    const { data } = await axios.get<StorageMaintenance>(
      `/api/v1/storage/vault/${vaultId}/maintenance`
    )
    return data
  },
  /**
   * Get storage space information for a vault
   */
  async getStorageSpace(vaultId: string): Promise<StorageSpaceResponse> {
    const response = await axios.get<StorageSpaceResponse>(`/api/v1/storage/vault/${vaultId}/space`)
    return response.data
  },

  /**
   * Get all items stored in vault storage.
   *
   * Uses the typed API boundary so callers can pass an AbortSignal and opt out
   * of the transport-level error toast (the Nuka-Cola count query does both).
   */
  async getStorageItems(
    vaultId: string,
    options: ApiRequestOptions = {}
  ): Promise<StorageItemsResponse> {
    return apiGet<StorageItemsResponse>(`/api/v1/storage/vault/${vaultId}/items`, options)
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

  /**
   * Open one unopened lunchbox and roll its contents into the vault
   */
  async openLunchbox(vaultId: string, itemId: string): Promise<LunchboxOpened> {
    const response = await axios.post<LunchboxOpened>(
      `/api/v1/storage/vault/${vaultId}/lunchbox/open`,
      { item_id: itemId } satisfies LunchboxOpenRequest
    )
    return response.data
  },
}
