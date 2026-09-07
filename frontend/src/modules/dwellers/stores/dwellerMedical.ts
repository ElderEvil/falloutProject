import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type { DwellerShort } from '../models/dweller'
import { getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useDwellerFilterStore } from './dwellerFilter'
import type { components } from '@/core/types/api.generated'

type MedicalSupply = 'stimpack' | 'radaway'
type MedicalTransferResponse = components['schemas']['MedicalTransferResponse']

export const useDwellerMedicalStore = defineStore('dwellerMedical', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()

  function applyDwellerUpdate(dwellerId: string, updated: DwellerShort): void {
    if (filterStore.detailedDwellers[dwellerId]) {
      Object.assign(filterStore.detailedDwellers[dwellerId], updated)
    }

    const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
    if (dwellerIndex !== -1) {
      filterStore.dwellers[dwellerIndex] = {
        ...filterStore.dwellers[dwellerIndex],
        ...updated,
      }
    }
  }

  async function useMedicalSupply(
    supply: MedicalSupply,
    dwellerId: string,
    token: string
  ): Promise<DwellerShort | null> {
    const label = supply === 'stimpack' ? 'stimpack' : 'RadAway'
    try {
      const response = await axios.post<DwellerShort>(
        `/api/v1/dwellers/${dwellerId}/use_${supply}`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      applyDwellerUpdate(dwellerId, response.data)

      toast.success(supply === 'stimpack' ? 'Stimpack used! Dweller healed.' : 'RadAway used! Radiation reduced.')
      return response.data
    } catch (error: unknown) {
      const errorMessage = getErrorMessage(error, `Failed to use ${label}`)
      handleStoreError(error, `Failed to use ${label} for dweller ${dwellerId}`, false)
      toast.error(errorMessage)
      return null
    }
  }

  async function useStimpack(dwellerId: string, token: string): Promise<DwellerShort | null> {
    return useMedicalSupply('stimpack', dwellerId, token)
  }

  async function useRadaway(dwellerId: string, token: string): Promise<DwellerShort | null> {
    return useMedicalSupply('radaway', dwellerId, token)
  }

  async function issueMedicalSupply(
    vaultId: string,
    dwellerId: string,
    supply: MedicalSupply,
    token: string
  ): Promise<MedicalTransferResponse | null> {
    try {
      const response = await axios.post<MedicalTransferResponse>(
        `/api/v1/storage/vault/${vaultId}/medical/transfer`,
        {
          dweller_id: dwellerId,
          stimpaks: supply === 'stimpack' ? 1 : 0,
          radaways: supply === 'radaway' ? 1 : 0,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )

      toast.success(`${supply === 'stimpack' ? 'Stimpack' : 'RadAway'} issued from vault storage`)
      return response.data
    } catch (error: unknown) {
      handleStoreError(error, `Failed to issue ${supply} to dweller ${dwellerId}`)
      return null
    }
  }

  return {
    useStimpack,
    useRadaway,
    issueMedicalSupply,
  }
})
