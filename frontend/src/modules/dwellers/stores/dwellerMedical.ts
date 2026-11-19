import { defineStore } from 'pinia'
import type { DwellerShort } from '../models/dweller'
import { notifyErrorOnce, getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useDwellerFilterStore } from './dwellerFilter'
import * as medicalApi from '../api/medical'
import type { components } from '@/core/types/api.generated'

type MedicalSupply = medicalApi.MedicalSupply
type MedicalTransferResponse = components['schemas']['MedicalTransferResponse']
type MedicalDistributionResponse = components['schemas']['MedicalDistributionResponse']

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
    dwellerId: string
  ): Promise<DwellerShort | null> {
    const label = supply === 'stimpack' ? 'stimpack' : 'RadAway'
    try {
      const updated = await medicalApi.useSupply(supply, dwellerId)
      applyDwellerUpdate(dwellerId, updated)
      toast.success(
        supply === 'stimpack'
          ? 'Stimpack used! Dweller healed.'
          : 'RadAway used! Radiation reduced.'
      )
      return updated
    } catch (error: unknown) {
      const errorMessage = getErrorMessage(error, `Failed to use ${label}`)
      handleStoreError(error, `Failed to use ${label} for dweller ${dwellerId}`, false)
      notifyErrorOnce(error, errorMessage)
      return null
    }
  }

  const useStimpack = (dwellerId: string) => useMedicalSupply('stimpack', dwellerId)

  const useRadaway = (dwellerId: string) => useMedicalSupply('radaway', dwellerId)

  async function issueMedicalSupply(
    vaultId: string,
    dwellerId: string,
    supply: MedicalSupply
  ): Promise<MedicalTransferResponse | null> {
    try {
      return await medicalApi.issueSupply(vaultId, dwellerId, supply)
    } catch (error: unknown) {
      handleStoreError(error, `Failed to issue ${supply} to dweller ${dwellerId}`)
      return null
    }
  }

  async function distributeRecoverySupplies(
    vaultId: string
  ): Promise<MedicalDistributionResponse | null> {
    try {
      const data = await medicalApi.distributeRecoverySupplies(vaultId)

      await filterStore.fetchDwellersByVault(vaultId)
      await filterStore.fetchAllDwellers(vaultId, false, true)

      const { dwellers_treated: treated, radaways_used: radaways, stimpaks_used: stimpaks } = data
      if (treated > 0) {
        toast.success(
          `Treated ${treated} dwellers with ${radaways} RadAway and ${stimpaks} Stimpack`
        )
      } else {
        toast.info('No irradiated dwellers needed treatment')
      }

      return data
    } catch (error: unknown) {
      handleStoreError(error, `Failed to treat irradiated dwellers in vault ${vaultId}`)
      return null
    }
  }

  return {
    useStimpack,
    useRadaway,
    issueMedicalSupply,
    distributeRecoverySupplies,
  }
})
