import { defineStore } from 'pinia'
import * as generationApi from '../api/generation'
import type { Dweller } from '../models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerFilterStore } from './dwellerFilter'

export const useDwellerGenerationStore = defineStore('dwellerGeneration', () => {
  const toast = useToast()
  const authStore = useAuthStore()
  const vaultStore = useVaultStore()
  const filterStore = useDwellerFilterStore()

  async function run(
    id: string,
    generate: (id: string) => Promise<Dweller>,
    successMessage: string,
    failurePrefix: string
  ): Promise<Dweller | null> {
    const session = authStore.sessionGeneration
    const vaultId = vaultStore.activeVaultId
    try {
      const data = await generate(id)
      if (session !== authStore.sessionGeneration || vaultId !== vaultStore.activeVaultId) {
        return null
      }
      filterStore.detailedDwellers[id] = data
      toast.success(successMessage)
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      handleStoreError(error, `${failurePrefix} for dweller ${id}`)
      return null
    }
  }

  const generateDwellerInfo = (id: string) =>
    run(
      id,
      generationApi.generateDwellerInfo,
      'Dweller info generated successfully!',
      'Failed to generate info'
    )

  const generateDwellerBio = (id: string) =>
    run(
      id,
      generationApi.generateDwellerBio,
      'Biography generated successfully!',
      'Failed to generate biography'
    )

  const extendDwellerBio = (id: string) =>
    run(
      id,
      generationApi.extendDwellerBio,
      'Biography extended successfully!',
      'Failed to extend biography'
    )

  const generateDwellerPortrait = (id: string) =>
    run(
      id,
      generationApi.generateDwellerPortrait,
      'Portrait generated successfully!',
      'Failed to generate portrait'
    )

  const generateDwellerAppearance = (id: string) =>
    run(
      id,
      generationApi.generateDwellerAppearance,
      'Appearance generated successfully!',
      'Failed to generate appearance'
    )

  return {
    generateDwellerInfo,
    generateDwellerBio,
    extendDwellerBio,
    generateDwellerPortrait,
    generateDwellerAppearance,
  }
})
