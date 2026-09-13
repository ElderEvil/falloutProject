import axios from '@/core/plugins/axios'
import type { CraftableItemType, CraftingOrder, CraftingRecipe, CraftResult } from '../models/crafting'

export const craftingService = {
  /** Craftable items of one type with their costs and affordability. */
  async listRecipes(vaultId: string, itemType: CraftableItemType): Promise<CraftingRecipe[]> {
    const response = await axios.get<{ recipes: CraftingRecipe[] }>(
      `/api/v1/crafting/vault/${vaultId}/recipes/${itemType}`,
    )
    return response.data.recipes
  },

  /** The vault's workshop queue, newest first. */
  async listOrders(vaultId: string): Promise<CraftingOrder[]> {
    const response = await axios.get<{ orders: CraftingOrder[] }>(
      `/api/v1/crafting/vault/${vaultId}/orders`,
    )
    return response.data.orders
  },

  /** Queue a craft; materials are consumed immediately. */
  async startOrder(vaultId: string, itemName: string, itemType: CraftableItemType): Promise<CraftingOrder> {
    const response = await axios.post<CraftingOrder>(`/api/v1/crafting/vault/${vaultId}/orders`, {
      item_name: itemName,
      item_type: itemType,
    })
    return response.data
  },

  /** Move a finished order's item into storage. */
  async collectOrder(vaultId: string, orderId: string): Promise<CraftResult> {
    const response = await axios.post<CraftResult>(
      `/api/v1/crafting/vault/${vaultId}/orders/${orderId}/collect`,
    )
    return response.data
  },
}
