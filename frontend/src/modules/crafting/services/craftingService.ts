import axios from '@/core/plugins/axios'
import type { CraftableItemType, CraftingRecipe, CraftResult } from '../models/crafting'

export const craftingService = {
  /** Craftable items of one type with their costs and affordability. */
  async listRecipes(vaultId: string, itemType: CraftableItemType): Promise<CraftingRecipe[]> {
    const response = await axios.get<{ recipes: CraftingRecipe[] }>(
      `/api/v1/crafting/vault/${vaultId}/recipes/${itemType}`,
    )
    return response.data.recipes
  },

  /** Consume materials and place the crafted item in storage. */
  async craft(vaultId: string, itemName: string, itemType: CraftableItemType): Promise<CraftResult> {
    const response = await axios.post<CraftResult>(`/api/v1/crafting/vault/${vaultId}/craft`, {
      item_name: itemName,
      item_type: itemType,
    })
    return response.data
  },
}
