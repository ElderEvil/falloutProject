import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as objectiveService from '../services/objectiveService'
import type { Objective, ObjectiveCreate } from '../models/objective'
import { refreshNukaColaCount } from '@/modules/vault/composables/useNukaColaCount'

export const useObjectivesStore = defineStore('objectives', () => {
  // State
  const objectives = ref<Objective[]>([])
  const objectivesVaultId = ref<string | null>(null)
  let fetchGeneration = 0

  // Actions
  async function fetchObjectives(vaultId: string, skip = 0, limit = 100): Promise<void> {
    const generation = ++fetchGeneration
    if (objectivesVaultId.value !== vaultId) objectives.value = []
    objectivesVaultId.value = vaultId
    const objectivesData = await objectiveService.fetchObjectives(vaultId, skip, limit)
    if (generation === fetchGeneration) objectives.value = objectivesData
  }

  async function addObjective(vaultId: string, objectiveData: ObjectiveCreate): Promise<void> {
    await objectiveService.addObjective(vaultId, objectiveData)
    await fetchObjectives(vaultId)
  }

  async function getObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    return objectiveService.getObjective(vaultId, objectiveId)
  }

  async function completeObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    const objective = objectives.value.find((item) => item.id === objectiveId)
    if (!objective) throw new Error('Objective no longer available')
    ++fetchGeneration
    const progress = await objectiveService.claimObjective(vaultId, objectiveId)
    void refreshNukaColaCount(vaultId)
    const completed = { ...objective, ...progress }
    if (objectivesVaultId.value === vaultId) {
      ++fetchGeneration
      const index = objectives.value.findIndex((item) => item.id === objectiveId)
      if (index !== -1) objectives.value[index] = completed
      // Claiming an achievement unlocks the next stage server-side.
      await fetchObjectives(vaultId)
    }
    return completed
  }

  async function updateProgress(
    vaultId: string,
    objectiveId: string,
    progress: number
  ): Promise<Objective> {
    const updated = await objectiveService.updateProgress(vaultId, objectiveId, progress)
    const index = objectives.value.findIndex((obj) => obj.id === objectiveId)
    if (index !== -1) {
      objectives.value[index] = updated
    }
    return updated
  }

  return {
    objectives,
    objectivesVaultId,
    fetchObjectives,
    addObjective,
    getObjective,
    completeObjective,
    updateProgress,
  }
})
