import { apiGet, apiPost } from '@/core/utils/api'
import type { DeliveryResult, Pregnancy } from '../models/pregnancy'

export const pregnancyApi = {
  getByVault: (vaultId: string) => apiGet<Pregnancy[]>(`/api/v1/pregnancies/vault/${vaultId}`),

  get: (pregnancyId: string) => apiGet<Pregnancy>(`/api/v1/pregnancies/${pregnancyId}`),

  deliver: (pregnancyId: string) =>
    apiPost<DeliveryResult>(`/api/v1/pregnancies/${pregnancyId}/deliver`),
}
