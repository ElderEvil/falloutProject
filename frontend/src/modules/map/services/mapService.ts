import axios from '@/core/plugins/axios'
import type { VaultMapResponse, WastelandLocationWithDwellers } from '../models/map'

export async function getVaultMap(token: string, vaultId: string): Promise<VaultMapResponse> {
  const response = await axios.get(`/api/v1/map/vault/${vaultId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export async function getLocationDetail(
  token: string,
  vaultId: string,
  locationId: string
): Promise<WastelandLocationWithDwellers> {
  const response = await axios.get(`/api/v1/map/vault/${vaultId}/locations/${locationId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}
