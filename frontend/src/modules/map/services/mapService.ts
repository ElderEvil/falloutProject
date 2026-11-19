import { apiGet } from '@/core/utils/api'
import type {
  VaultMapResponse,
  WastelandLocationWithDwellers,
  WorldSnapshotRead,
} from '../models/map'

export async function getWorldSnapshot(): Promise<WorldSnapshotRead> {
  return apiGet<WorldSnapshotRead>('/api/v1/map/world', { skipErrorNotification: true })
}

export async function getVaultMap(vaultId: string): Promise<VaultMapResponse> {
  return apiGet<VaultMapResponse>(`/api/v1/map/vault/${vaultId}`)
}

export async function getLocationDetail(
  vaultId: string,
  locationId: string
): Promise<WastelandLocationWithDwellers> {
  return apiGet<WastelandLocationWithDwellers>(
    `/api/v1/map/vault/${vaultId}/locations/${locationId}`
  )
}
