import axios from '@/core/plugins/axios'
import type { Incident, IncidentListResponse, IncidentResolveResponse } from '../models/incident'

export const incidentApi = {
  /**
   * Get all active incidents for a vault
   */
  async getActiveIncidents(vaultId: string, token: string): Promise<IncidentListResponse> {
    const response = await axios.get(
      `/api/v1/game/vaults/${vaultId}/incidents`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    )
    return response.data
  },

  /**
   * Get detailed information about a specific incident
   */
  async getIncident(vaultId: string, incidentId: string, token: string): Promise<Incident> {
    const response = await axios.get(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    )
    return response.data
  },

  /**
   * Manually resolve an incident
   */
  async resolveIncident(
    vaultId: string,
    incidentId: string,
    token: string,
    success: boolean = true
  ): Promise<IncidentResolveResponse> {
    const response = await axios.post(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/resolve`,
      null,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        params: {
          success,
        },
      }
    )
    return response.data
  },

  /**
   * [DEBUG] Spawn an incident for testing purposes
   */
  async spawnIncident(vaultId: string, token: string, incidentType?: string): Promise<any> {
    const response = await axios.post(
      `/api/v1/game/vaults/${vaultId}/incidents/spawn`,
      null,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        params: incidentType ? { incident_type: incidentType } : {},
      }
    )
    return response.data
  },
}
