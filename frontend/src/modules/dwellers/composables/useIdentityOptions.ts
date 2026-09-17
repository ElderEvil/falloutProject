import { ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { handleStoreError } from '@/core/utils/errorHandler'
import { getIdentityOptions } from '../services/dwellerService'

export function useIdentityOptions() {
  const authStore = useAuthStore()
  const races = ref<string[]>([])
  const factionsByRace = ref<Record<string, string[]>>({})
  const statesByRace = ref<Record<string, string[]>>({})
  const loaded = ref(false)

  async function load(): Promise<void> {
    if (!authStore.token) return
    try {
      const options = await getIdentityOptions(authStore.token)
      races.value = options.races ?? []
      factionsByRace.value = options.factions_by_race ?? {}
      statesByRace.value = options.states_by_race ?? {}
      loaded.value = true
    } catch (error) {
      handleStoreError(error, 'Failed to load identity options', false)
    }
  }

  function factionsFor(race: string): string[] {
    return factionsByRace.value[race] ?? factionsByRace.value.human ?? []
  }

  return { races, factionsByRace, statesByRace, loaded, load, factionsFor }
}
