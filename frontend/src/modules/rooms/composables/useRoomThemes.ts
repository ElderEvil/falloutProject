import { ref, watch, type Ref } from 'vue'
import { craftingService } from '@/modules/crafting/services/craftingService'
import { getErrorMessage } from '@/core/utils/errorHandler'
import type { RoomStyleValue } from '../models/room'

export function useRoomThemes(vaultId: string, enabled: Ref<boolean>) {
  const availableThemes = ref<RoomStyleValue[]>([])

  async function load() {
    if (!enabled.value) {
      availableThemes.value = []
      return
    }
    try {
      const recipes = await craftingService.listRecipes(vaultId, 'theme')
      availableThemes.value = recipes
        .filter((recipe) => recipe.owned && recipe.style)
        .map((recipe) => recipe.style as RoomStyleValue)
    } catch (error) {
      console.warn('[useRoomThemes] Failed to load room themes:', getErrorMessage(error))
      availableThemes.value = []
    }
  }

  watch([() => vaultId, enabled], load, { immediate: true })

  return { availableThemes, reloadThemes: load }
}
