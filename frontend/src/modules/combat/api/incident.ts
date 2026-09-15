import axios from '@/core/plugins/axios'
import type { Incident, IncidentListResponse, IncidentOverflowResponse } from '../models/incident'

export const incidentApi = {
  /**
   * Get all active incidents for a vault
   */
  async getActiveIncidents(vaultId: string, token: string): Promise<IncidentListResponse> {
    const response = await axios.get(`/api/v1/game/vaults/${vaultId}/incidents`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
    return response.data
  },

  /**
   * Get detailed information about a specific incident
   */
  async getIncident(vaultId: string, incidentId: string, token: string): Promise<Incident> {
    const response = await axios.get(`/api/v1/game/vaults/${vaultId}/incidents/${incidentId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
    return response.data
  },

  async assignResponders(vaultId: string, incidentId: string, dwellerIds: string[], token: string): Promise<void> {
    await axios.post(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/responders`,
      { dweller_ids: dwellerIds },
      { headers: { Authorization: `Bearer ${token}` } }
    )
  },

  /**
   * Store one held incident item; 409 while storage is still full
   */
  async takeOverflow(
    vaultId: string,
    incidentId: string,
    index: number,
    token: string
  ): Promise<IncidentOverflowResponse> {
    const response = await axios.post(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/overflow/take`,
      { index },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    return response.data
  },

  /**
   * Sell one held incident item for caps; needs no storage space
   */
  async sellOverflow(
    vaultId: string,
    incidentId: string,
    index: number,
    token: string
  ): Promise<IncidentOverflowResponse> {
    const response = await axios.post(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/overflow/sell`,
      { index },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    return response.data
  },

  /**
   * [DEBUG] Spawn an incident for testing purposes
   */
  async spawnIncident(vaultId: string, token: string, incidentType?: string): Promise<any> {
    const response = await axios.post(`/api/v1/game/vaults/${vaultId}/incidents/spawn`, null, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      params: incidentType ? { incident_type: incidentType } : {},
    })
    return response.data
  },
}
