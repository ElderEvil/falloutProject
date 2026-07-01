import { apiGet, apiPost } from '@/core/plugins/httpClient'
import type { Incident, IncidentListResponse, IncidentResolveResponse } from '../models/incident'

export const incidentApi = {
  /**
   * Get all active incidents for a vault
   */
  async getActiveIncidents(vaultId: string): Promise<IncidentListResponse> {
    return apiGet<IncidentListResponse>(`/api/v1/game/vaults/${vaultId}/incidents`)
  },

  /**
   * Get detailed information about a specific incident
   */
  async getIncident(vaultId: string, incidentId: string): Promise<Incident> {
    return apiGet<Incident>(`/api/v1/game/vaults/${vaultId}/incidents/${incidentId}`)
  },

  /**
   * Manually resolve an incident
   */
  async resolveIncident(
    vaultId: string,
    incidentId: string,
    success: boolean = true
  ): Promise<IncidentResolveResponse> {
    return apiPost<IncidentResolveResponse>(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/resolve?success=${success}`
    )
  },

  /**
   * [DEBUG] Spawn an incident for testing purposes
   */
  async spawnIncident(vaultId: string, incidentType?: string): Promise<Incident> {
    const params = new URLSearchParams()
    if (incidentType) {
      params.set('incident_type', incidentType)
    }
    const queryString = params.toString()
    const url = queryString
      ? `/api/v1/game/vaults/${vaultId}/incidents/spawn?${queryString}`
      : `/api/v1/game/vaults/${vaultId}/incidents/spawn`
    return apiPost<Incident>(url)
  },
}
