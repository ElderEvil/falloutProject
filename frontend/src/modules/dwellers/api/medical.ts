import type { components } from '@/core/types/api.generated'
import { apiPost } from '@/core/utils/api'
import type { DwellerShort } from '../models/dweller'

export type MedicalSupply = 'stimpack' | 'radaway'

type MedicalTransferResponse = components['schemas']['MedicalTransferResponse']
type MedicalDistributionResponse = components['schemas']['MedicalDistributionResponse']

export function useSupply(supply: MedicalSupply, dwellerId: string): Promise<DwellerShort> {
  return apiPost<DwellerShort>(`/api/v1/dwellers/${dwellerId}/use_${supply}`)
}

export function issueSupply(
  vaultId: string,
  dwellerId: string,
  supply: MedicalSupply
): Promise<MedicalTransferResponse> {
  return apiPost<MedicalTransferResponse>(`/api/v1/storage/vault/${vaultId}/medical/transfer`, {
    dweller_id: dwellerId,
    stimpaks: supply === 'stimpack' ? 1 : 0,
    radaways: supply === 'radaway' ? 1 : 0,
  })
}

export function distributeRecoverySupplies(vaultId: string): Promise<MedicalDistributionResponse> {
  return apiPost<MedicalDistributionResponse>(
    `/api/v1/storage/vault/${vaultId}/medical/distribute-recovery-supplies`
  )
}
