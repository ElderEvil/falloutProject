import { defineStore, acceptHMRUpdate } from 'pinia'
import * as http from '@/core/plugins/httpClient'
import type { DwellerShort } from '../models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useDwellerFilterStore } from './dwellerFilter'

export const useDwellerMedicalStore = defineStore('dwellerMedical', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()

  async function useStimpack(dwellerId: string, token: string): Promise<DwellerShort | null> {
    try {
      const response = await http.apiPost<DwellerShort>(
        `/api/v1/dwellers/${dwellerId}/use_stimpack`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Update detailed dweller if cached
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = {
          ...filterStore.detailedDwellers[dwellerId],
          ...response,
        } as import('../models/dweller').Dweller
      }

      // Update in list if exists
      const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        filterStore.dwellers[dwellerIndex] = {
          ...filterStore.dwellers[dwellerIndex],
          ...response,
        }
      }

      toast.success('Stimpack used! Dweller healed.')
      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to use stimpack'
      handleStoreError(error, `Failed to use stimpack for dweller ${dwellerId}`)
      toast.error(errorMessage)
      return null
    }
  }

  async function useRadaway(dwellerId: string, token: string): Promise<DwellerShort | null> {
    try {
      const response = await http.apiPost<DwellerShort>(
        `/api/v1/dwellers/${dwellerId}/use_radaway`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Update detailed dweller if cached
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = {
          ...filterStore.detailedDwellers[dwellerId],
          ...response,
        } as import('../models/dweller').Dweller
      }

      // Update in list if exists
      const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        filterStore.dwellers[dwellerIndex] = {
          ...filterStore.dwellers[dwellerIndex],
          ...response,
        }
      }

      toast.success('RadAway used! Radiation reduced.')
      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to use RadAway'
      handleStoreError(error, `Failed to use radaway for dweller ${dwellerId}`)
      toast.error(errorMessage)
      return null
    }
  }

  return {
    useStimpack,
    useRadaway,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDwellerMedicalStore, import.meta.hot))
}
