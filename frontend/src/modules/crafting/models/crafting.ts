import type { components } from '@/core/types/api.generated'

export type CraftingRecipe = components['schemas']['CraftingRecipeRead']
export type CraftResult = components['schemas']['CraftResultRead']
export type CraftingOrder = components['schemas']['CraftingOrderRead']
export type CraftableItemType = 'weapon' | 'outfit'
