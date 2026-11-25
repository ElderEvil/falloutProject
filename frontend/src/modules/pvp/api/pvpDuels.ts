import { apiGet, apiPost } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

export type PvpDuel = components['schemas']['PvpDuelRead']
export type PvpBoardEntry = components['schemas']['PvpDuelBoardEntry']

const base = (vaultId: string) => `/api/v1/vaults/${vaultId}/pvp-duels`

export const pvpDuelApi = {
  list: (vaultId: string) => apiGet<PvpBoardEntry[]>(base(vaultId)),
  get: (vaultId: string, duelId: string) => apiGet<PvpDuel>(`${base(vaultId)}/${duelId}`),
  post: (vaultId: string, dwellerIds: string[]) =>
    apiPost<PvpDuel>(base(vaultId), { dweller_ids: dwellerIds }),
  accept: (vaultId: string, duelId: string, dwellerIds: string[]) =>
    apiPost<PvpDuel>(`${base(vaultId)}/${duelId}/accept`, { dweller_ids: dwellerIds }),
}
