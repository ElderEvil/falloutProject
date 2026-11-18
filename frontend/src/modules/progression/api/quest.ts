import type { components } from '@/core/types/api.generated'
import { apiGet, apiPost } from '@/core/utils/api'
import type { Quest, QuestPartyMember, VaultQuest } from '../models/quest'

type QuestCompleteResponse = components['schemas']['QuestCompleteResponse']

export interface EligibleDweller {
  id: string
  first_name: string
  last_name: string | null
  level: number
  rarity: string
}

export function listQuests(): Promise<Quest[]> {
  return apiGet<Quest[]>('/api/v1/quests/')
}

export async function listVaultQuests(vaultId: string): Promise<VaultQuest[]> {
  const data = await apiGet<unknown>(`/api/v1/quests/${vaultId}/`)
  if (!Array.isArray(data)) {
    throw new TypeError('Expected a list of vault quests')
  }
  return data as VaultQuest[]
}

export function assignQuest(vaultId: string, questId: string, isVisible = true): Promise<void> {
  return apiPost(`/api/v1/quests/${vaultId}/${questId}/assign`, null, {
    params: { is_visible: isVisible },
  })
}

export function claimRewards(vaultId: string, questId: string): Promise<QuestCompleteResponse> {
  return apiPost<QuestCompleteResponse>(`/api/v1/quests/${vaultId}/${questId}/claim-rewards`)
}

export function getParty(vaultId: string, questId: string): Promise<QuestPartyMember[]> {
  return apiGet<QuestPartyMember[]>(`/api/v1/quests/${vaultId}/${questId}/party`)
}

export function getEligibleDwellers(vaultId: string, questId: string): Promise<EligibleDweller[]> {
  return apiGet<EligibleDweller[]>(`/api/v1/quests/${vaultId}/${questId}/eligible-dwellers`)
}

export function startQuest(vaultId: string, questId: string, dwellerIds?: string[]): Promise<void> {
  return apiPost(
    `/api/v1/quests/${vaultId}/${questId}/start`,
    dwellerIds ? { dweller_ids: dwellerIds } : undefined
  )
}
