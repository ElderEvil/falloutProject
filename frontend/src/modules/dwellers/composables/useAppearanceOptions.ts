import { ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { handleStoreError } from '@/core/utils/errorHandler'
import { getAppearanceOptions } from '../services/dwellerService'

export function useAppearanceOptions() {
  const authStore = useAuthStore()
  const skinTonesByRace = ref<Record<string, string[]>>({})
  const buildsByRace = ref<Record<string, string[]>>({})
  const haircutsByRace = ref<Record<string, string[]>>({})
  const headgearByRace = ref<Record<string, string[]>>({})
  const expressions = ref<string[]>([])
  const poses = ref<string[]>([])
  const backgrounds = ref<string[]>([])
  const heights = ref<string[]>([])
  const eyeColors = ref<string[]>([])
  const hairColors = ref<string[]>([])
  const loaded = ref(false)

  async function load(): Promise<void> {
    if (!authStore.token) return
    try {
      const options = await getAppearanceOptions(authStore.token)
      skinTonesByRace.value = options.skin_tones_by_race ?? {}
      buildsByRace.value = options.builds_by_race ?? {}
      haircutsByRace.value = options.haircuts_by_race ?? {}
      headgearByRace.value = options.headgear_by_race ?? {}
      expressions.value = options.expressions ?? []
      poses.value = options.poses ?? []
      backgrounds.value = options.backgrounds ?? []
      heights.value = options.heights ?? []
      eyeColors.value = options.eye_colors ?? []
      hairColors.value = options.hair_colors ?? []
      loaded.value = true
    } catch (error) {
      handleStoreError(error, 'Failed to load appearance options', false)
    }
  }

  return {
    skinTonesByRace,
    buildsByRace,
    haircutsByRace,
    headgearByRace,
    expressions,
    poses,
    backgrounds,
    heights,
    eyeColors,
    hairColors,
    loaded,
    load,
  }
}
