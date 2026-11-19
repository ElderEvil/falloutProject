import { apiGet, apiPost } from '@/core/utils/api'
import type {
  CraftableItemType,
  CraftingOrder,
  CraftingRecipe,
  CraftResult,
} from '../models/crafting'

export const craftingService = {
  /** Craftable items of one type with their costs and affordability. */
  async listRecipes(vaultId: string, itemType: CraftableItemType): Promise<CraftingRecipe[]> {
    const data = await apiGet<{ recipes: CraftingRecipe[] }>(
      `/api/v1/crafting/vault/${vaultId}/recipes/${itemType}`
    )
    return data.recipes
  },

  /** The vault's workshop queue, newest first. */
  async listOrders(vaultId: string): Promise<CraftingOrder[]> {
    const data = await apiGet<{ orders: CraftingOrder[] }>(
      `/api/v1/crafting/vault/${vaultId}/orders`
    )
    return data.orders
  },

  /** Queue a craft; materials are consumed immediately. */
  async startOrder(
    vaultId: string,
    itemName: string,
    itemType: CraftableItemType
  ): Promise<CraftingOrder> {
    return apiPost<CraftingOrder>(`/api/v1/crafting/vault/${vaultId}/orders`, {
      item_name: itemName,
      item_type: itemType,
    })
  },

  /** Cancel an active order, refunding its caps and junk. */
  async cancelOrder(vaultId: string, orderId: string): Promise<CraftingOrder> {
    return apiPost<CraftingOrder>(`/api/v1/crafting/vault/${vaultId}/orders/${orderId}/cancel`)
  },

  /** Move a finished order's item into storage. */
  async collectOrder(vaultId: string, orderId: string): Promise<CraftResult> {
    return apiPost<CraftResult>(`/api/v1/crafting/vault/${vaultId}/orders/${orderId}/collect`)
  },
}
