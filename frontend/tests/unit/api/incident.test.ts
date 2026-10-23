import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
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

    expect(axios.get).toHaveBeenCalledWith(
      '/api/v1/game/vaults/vault-1/incidents/incident-1/team',
      {
        headers: { Authorization: 'Bearer token' },
      }
    )
    expect(team).toEqual([teamMember])
  })
})

describe('incidentApi.takeOverflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('leaves the actionable storage-full error to the incident store', async () => {
    vi.mocked(axios.post).mockResolvedValueOnce({ data: { unclaimed_loot: [], caps_granted: 0 } })

    await incidentApi.takeOverflow('vault-1', 'incident-1', 2, 'token')

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/game/vaults/vault-1/incidents/incident-1/overflow/take',
      { index: 2 },
      {
        headers: { Authorization: 'Bearer token' },
        _skipErrorNotification: true,
      }
    )
  })
})

it('returns the responders actually accepted by the backend', async () => {
  const result = {
    incident_id: 'incident-1',
    room_id: 'room-1',
    assigned_dweller_ids: ['dweller-1'],
  }
  vi.mocked(axios.post).mockResolvedValueOnce({ data: result })
  expect(
    await incidentApi.assignResponders('vault-1', 'incident-1', ['dweller-1', 'dweller-2'], 'token')
  ).toEqual(result)
})
