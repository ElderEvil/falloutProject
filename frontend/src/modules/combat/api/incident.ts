import type { components } from '@/core/types/api.generated'
import { apiGet, apiPost } from '@/core/utils/api'
import type {
  Incident,
  IncidentListResponse,
  IncidentOverflowResponse,
  IncidentTeamMember,
  IncidentRespondersResponse,
} from '../models/incident'

type IncidentSpawnResponse = components['schemas']['IncidentSpawnResponse']

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

  async assignResponders(
    vaultId: string,
    incidentId: string,
    dwellerIds: string[]
  ): Promise<IncidentRespondersResponse> {
    return apiPost<IncidentRespondersResponse>(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/responders`,
      { dweller_ids: dwellerIds }
    )
  },

  /**
   * Get the designated responder team for an incident
   */
  async getIncidentTeam(vaultId: string, incidentId: string): Promise<IncidentTeamMember[]> {
    return apiGet<IncidentTeamMember[]>(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/team`
    )
  },

  /**
   * Store one held incident item; 409 while storage is still full
   */
  async takeOverflow(
    vaultId: string,
    incidentId: string,
    index: number
  ): Promise<IncidentOverflowResponse> {
    return apiPost<IncidentOverflowResponse>(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/overflow/take`,
      { index },
      { skipErrorNotification: true }
    )
  },

  /**
   * Sell one held incident item for caps; needs no storage space
   */
  async sellOverflow(
    vaultId: string,
    incidentId: string,
    index: number
  ): Promise<IncidentOverflowResponse> {
    return apiPost<IncidentOverflowResponse>(
      `/api/v1/game/vaults/${vaultId}/incidents/${incidentId}/overflow/sell`,
      { index }
    )
  },

  /**
   * [DEBUG] Spawn an incident for testing purposes
   */
  async spawnIncident(vaultId: string, incidentType?: string): Promise<IncidentSpawnResponse> {
    return apiPost(`/api/v1/game/vaults/${vaultId}/incidents/spawn`, null, {
      params: incidentType ? { incident_type: incidentType } : {},
    })
  },
}
