import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { incidentApi } from '@/modules/combat/api/incident'
import type { IncidentTeamMember } from '@/modules/combat/models/incident'

vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const teamMember: IncidentTeamMember = {
  id: 'tm-1',
  team_id: 'team-1',
  dweller_id: 'dweller-1',
  slot_number: 1,
  status: 'assigned',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

describe('incidentApi.getIncidentTeam', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('hits the team endpoint with the auth header and returns the roster', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: [teamMember] })

    const team = await incidentApi.getIncidentTeam('vault-1', 'incident-1', 'token')

    expect(axios.get).toHaveBeenCalledWith('/api/v1/game/vaults/vault-1/incidents/incident-1/team', {
      headers: { Authorization: 'Bearer token' },
    })
    expect(team).toEqual([teamMember])
  })
})