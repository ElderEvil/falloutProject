import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { explorationApi } from '@/modules/exploration/api/exploration'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

describe('explorationApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('dispatches a party through the query parameter', async () => {
    const exploration = { id: 'exploration-1' }
    vi.mocked(axios.post).mockResolvedValue({ data: exploration })

    await expect(
      explorationApi.dispatchToLocation('vault-1', {
        dwellerIds: ['dweller-1'],
        locationId: 'loc-1',
        stimpaks: 2,
        radaways: 1,
      })
    ).resolves.toEqual(exploration)

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/explorations/dispatch',
      {
        dweller_ids: ['dweller-1'],
        location_id: 'loc-1',
        stimpaks: 2,
        radaways: 1,
      },
      { params: { vault_id: 'vault-1' } }
    )
  })

  it('suggests a heading through the query parameters', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: { heading_degrees: 135 } })

    await expect(explorationApi.suggestHeading('vault-1', 'seed-1', 8)).resolves.toBe(135)

    expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/suggest-heading', {
      params: { vault_id: 'vault-1', seed: 'seed-1', duration: 8 },
    })
  })

  it('returns null when the server has no heading suggestion', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: { heading_degrees: null } })

    await expect(explorationApi.suggestHeading('vault-1', 'seed-1', 8)).resolves.toBeNull()
  })

  it('loads the slot-ordered party for an exploration', async () => {
    const party = [{ id: 'member-1', slot_number: 1 }]
    vi.mocked(axios.get).mockResolvedValue({ data: party })

    await expect(explorationApi.getExplorationParty('vault-1', 'exploration-1')).resolves.toEqual(
      party
    )

    expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/vault/vault-1/exploration-1/party')
  })

  it('sends a dweller with the vault query parameter', async () => {
    const exploration = { id: 'exploration-1' }
    vi.mocked(axios.post).mockResolvedValue({ data: exploration })

    await expect(
      explorationApi.sendDwellerToWasteland('vault-1', {
        dweller_id: 'dweller-1',
        duration: 4,
        stimpaks: 0,
        radaways: 0,
        heading_degrees: 90,
      })
    ).resolves.toEqual(exploration)

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/explorations/send',
      {
        dweller_id: 'dweller-1',
        duration: 4,
        stimpaks: 0,
        radaways: 0,
        heading_degrees: 90,
      },
      { params: { vault_id: 'vault-1' } }
    )
  })

  it.each([true, false])('lists a vault runs with active_only=%s', async (activeOnly) => {
    const explorations = [{ id: 'exploration-1' }]
    vi.mocked(axios.get).mockResolvedValue({ data: explorations })

    await expect(explorationApi.getExplorationsByVault('vault-1', activeOnly)).resolves.toEqual(
      explorations
    )

    expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/vault/vault-1', {
      params: { active_only: activeOnly },
    })
  })

  it('loads one exploration by id', async () => {
    const exploration = { id: 'exploration-1' }
    vi.mocked(axios.get).mockResolvedValue({ data: exploration })

    await expect(explorationApi.getExploration('exploration-1')).resolves.toEqual(exploration)

    expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/exploration-1')
  })

  it('loads the progress snapshot by id', async () => {
    const progress = { id: 'exploration-1', progress_percentage: 50 }
    vi.mocked(axios.get).mockResolvedValue({ data: progress })

    await expect(explorationApi.getExplorationProgress('exploration-1')).resolves.toEqual(progress)

    expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/exploration-1/progress')
  })

  it('recalls an exploration with an empty body', async () => {
    const response = { exploration: { id: 'exploration-1' }, rewards_summary: null }
    vi.mocked(axios.post).mockResolvedValue({ data: response })

    await expect(explorationApi.recallDweller('exploration-1')).resolves.toEqual(response)

    expect(axios.post).toHaveBeenCalledWith('/api/v1/explorations/exploration-1/recall', {})
  })

  it('completes an exploration with an empty body', async () => {
    const response = { exploration: { id: 'exploration-1' }, rewards_summary: { caps: 10 } }
    vi.mocked(axios.post).mockResolvedValue({ data: response })

    await expect(explorationApi.completeExploration('exploration-1')).resolves.toEqual(response)

    expect(axios.post).toHaveBeenCalledWith('/api/v1/explorations/exploration-1/complete', {})
  })

  it('resolves an overflow item without a duplicate error toast', async () => {
    const response = { caps_granted: 25, unclaimed_loot: [] }
    vi.mocked(axios.post).mockResolvedValue({ data: response })

    await expect(explorationApi.resolveOverflowItem('exploration-1', 'sell', 0)).resolves.toEqual(
      response
    )

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/explorations/exploration-1/overflow/sell',
      { index: 0 },
      { _skipErrorNotification: true }
    )
  })

  it('loads pending overflow loot for a vault', async () => {
    const pending = [{ exploration_id: 'exploration-1', dweller_id: 'dweller-1' }]
    vi.mocked(axios.get).mockResolvedValue({ data: pending })

    await expect(explorationApi.getPendingOverflow('vault-1')).resolves.toEqual(pending)

    expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/vault/vault-1/pending-overflow')
  })
})
