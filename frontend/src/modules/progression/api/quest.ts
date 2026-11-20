import type { components } from '@/core/types/api.generated'
import { apiGet, apiPost } from '@/core/utils/api'
import type { QuestPartyMember, QuestRequirement, QuestReward, VaultQuest } from '../models/quest'

type QuestCompleteResponse = components['schemas']['QuestCompleteResponse']
type EligibleDwellerRead = components['schemas']['EligibleDwellerRead']
type QuestPartyMemberRead = components['schemas']['QuestPartyMemberRead']
type QuestRead = components['schemas']['QuestRead']
type QuestRequirementRead = components['schemas']['QuestRequirementRead']
type QuestRewardRead = components['schemas']['QuestRewardRead']

export interface EligibleDweller {
  id: string
  first_name: string
  last_name: string | null
  level: number
  rarity: string
}

function toQuestRequirement(requirement: QuestRequirementRead, questId: string): QuestRequirement {
  return {
    ...requirement,
    quest_id: questId,
    requirement_type: requirement.requirement_type as QuestRequirement['requirement_type'],
  }
}

function toQuestReward(reward: QuestRewardRead, questId: string): QuestReward {
  return {
    ...reward,
    quest_id: questId,
    reward_type: reward.reward_type as QuestReward['reward_type'],
    item_data: reward.item_data ?? undefined,
  }
}

function toVaultQuest(quest: QuestRead): VaultQuest {
  return {
    ...quest,
    quest_category: quest.quest_category ?? null,
    chain_id: quest.chain_id ?? null,
    previous_quest_id: quest.previous_quest_id ?? null,
    next_quest_id: quest.next_quest_id ?? null,
    created_at: '',
    updated_at: '',
    lock_reason: quest.lock_reason ?? null,
    started_at: quest.started_at ?? null,
    duration_minutes: quest.duration_minutes ?? null,
    return_started_at: quest.return_started_at ?? null,
    return_completes_at: quest.return_completes_at ?? null,
    completed_at: quest.completed_at ?? null,
    quest_requirements: quest.quest_requirements?.map((item) => toQuestRequirement(item, quest.id)),
    quest_rewards: quest.quest_rewards?.map((item) => toQuestReward(item, quest.id)),
  }
}

function toQuestPartyMember(member: QuestPartyMemberRead): QuestPartyMember {
  return {
    ...member,
    status: member.status as QuestPartyMember['status'],
    created_at: member.created_at ?? '',
    updated_at: member.updated_at ?? '',
  }
}

function toEligibleDweller(dweller: EligibleDwellerRead): EligibleDweller {
  return { ...dweller, last_name: dweller.last_name ?? null }
}

// One request per list: the server paginates over stable membership, so a client loop
// can skip rows when the reveal window shifts between pages.
const QUEST_LIST_LIMIT = 1000

export function listQuests(): Promise<QuestRead[]> {
  return apiGet<QuestRead[]>('/api/v1/quests/', { params: { limit: QUEST_LIST_LIMIT } })
}

const VAULT_QUEST_PAGE_SIZE = 100
const VAULT_QUEST_PAGE_CAP = 100

export async function listVaultQuests(vaultId: string): Promise<VaultQuest[]> {
  const all: VaultQuest[] = []
  for (
    let skip = 0;
    skip < VAULT_QUEST_PAGE_SIZE * VAULT_QUEST_PAGE_CAP;
    skip += VAULT_QUEST_PAGE_SIZE
  ) {
    const data = await apiGet<unknown>(`/api/v1/quests/${vaultId}/`, {
      params: { skip, limit: VAULT_QUEST_PAGE_SIZE },
    })
    if (!Array.isArray(data)) {
      throw new TypeError('Expected a list of vault quests')
    }
    all.push(...(data as QuestRead[]).map(toVaultQuest))
    if (data.length < VAULT_QUEST_PAGE_SIZE) {
      return all
    }
  }
  return all
}

export function assignQuest(vaultId: string, questId: string, isVisible = true): Promise<void> {
  return apiPost(`/api/v1/quests/${vaultId}/${questId}/assign`, null, {
    params: { is_visible: isVisible },
  })
}

export function claimRewards(vaultId: string, questId: string): Promise<QuestCompleteResponse> {
  return apiPost<QuestCompleteResponse>(`/api/v1/quests/${vaultId}/${questId}/claim-rewards`)
}

export async function getParty(vaultId: string, questId: string): Promise<QuestPartyMember[]> {
  const data = await apiGet<QuestPartyMemberRead[]>(`/api/v1/quests/${vaultId}/${questId}/party`)
  return data.map(toQuestPartyMember)
}

export async function getEligibleDwellers(
  vaultId: string,
  questId: string
): Promise<EligibleDweller[]> {
  const data = await apiGet<EligibleDwellerRead[]>(
    `/api/v1/quests/${vaultId}/${questId}/eligible-dwellers`
  )
  return data.map(toEligibleDweller)
}

export function startQuest(vaultId: string, questId: string, dwellerIds?: string[]): Promise<void> {
  return apiPost(
    `/api/v1/quests/${vaultId}/${questId}/start`,
    dwellerIds ? { dweller_ids: dwellerIds } : undefined
  )
}
