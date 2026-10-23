import type { SoundKey } from '@/core/audio/soundManifest'
import type { components } from '@/core/types/api.generated'

export interface NotificationNavigationContext {
  vault_id?: string | null
  from_dweller_id?: string | null
  notification_type: string
  meta_data?: Record<string, unknown> | null
}

const NOTIFICATION_SOUNDS = {
  exploration_update: 'explorationLoot',
  exploration_complete: 'explorationComplete',
  level_up: 'levelUp',
  training_complete: 'trainingComplete',
  training_started: 'trainingStart',
  crafting_complete: 'craftComplete',
  storage_item_degraded: 'resourceLow',
  storage_item_upgraded: 'craftComplete',
  recipe_unlocked: 'recipeUnlocked',
  relationship_formed: 'relationshipFormed',
  pregnancy_detected: 'pregnancyDetected',
  baby_born: 'babyBorn',
  child_adopted: 'babyBorn',
  // The incident store already plays the per-threat and victory/defeat cues when
  // the incident stream updates, so the bell stays on the generic alert here.
  combat_started: 'notification',
  combat_victory: 'notification',
  combat_defeat: 'notification',
  arena_morale_boost: 'arenaMorale',
  dweller_injured: 'dwellerInjured',
  dweller_died: 'dwellerDied',
  dweller_exit_requested: 'dwellerExit',
  hazard_team_joined: 'hazardTeamJoined',
  resource_low: 'resourceLow',
  resource_critical: 'resourceCritical',
  power_outage: 'powerOutage',
  quest_complete: 'questComplete',
  objective_completed: 'objectiveReady',
  objectives_refreshed: 'objectivesRefreshed',
  achievement_unlocked: 'success',
  radio_new_dweller: 'radioRecruit',
  radio_auto_switched_to_happiness: 'tabSwitch',
  map_registration_failed: 'mapRegistrationFailed',
  location_cleared: 'locationCleared',
  location_ready: 'locationReady',
} as const satisfies Record<components['schemas']['NotificationType'], SoundKey>

/** Resolve a notification type to its bell cue, falling back to the generic alert. */
export function getNotificationSound(notificationType: string): SoundKey {
  return NOTIFICATION_SOUNDS[notificationType as keyof typeof NOTIFICATION_SOUNDS] ?? 'notification'
}

function metadataString(notification: NotificationNavigationContext, key: string): string | null {
  const value = notification.meta_data?.[key]
  return typeof value === 'string' && value.length > 0 ? value : null
}

/**
 * Resolves a bell notification to the most specific screen that can act on it.
 * Older notifications may lack context, so each route has a safe vault-level fallback.
 */
export function getNotificationRoute(notification: NotificationNavigationContext): string | null {
  const vaultId = notification.vault_id ?? metadataString(notification, 'vault_id')
  if (!vaultId) return null

  const vaultPath = `/vault/${vaultId}`
  const dwellerId = metadataString(notification, 'dweller_id') ?? notification.from_dweller_id

  switch (notification.notification_type) {
    case 'exploration_complete':
    case 'exploration_update':
      return `${vaultPath}/exploration`
    case 'training_complete': {
      if (dwellerId) {
        const statName = metadataString(notification, 'stat_name')
        const statParam = statName
          ? `?tab=stats&stat=${encodeURIComponent(statName)}`
          : '?tab=stats'
        return `${vaultPath}/dwellers/${dwellerId}${statParam}`
      }
      return `${vaultPath}/training`
    }
    case 'storage_item_degraded':
    case 'storage_item_upgraded':
      return `${vaultPath}/storage`
    case 'training_started':
      return `${vaultPath}/training`
    case 'quest_complete': {
      const questId = metadataString(notification, 'quest_id')
      if (questId && notification.meta_data?.ready_to_claim === true) {
        return `${vaultPath}/quests?claimQuest=${encodeURIComponent(questId)}`
      }
      return `${vaultPath}/quests`
    }
    case 'level_up':
    case 'hazard_team_joined':
    case 'dweller_died':
    case 'dweller_injured':
    case 'dweller_exit_requested':
    case 'baby_born':
    case 'child_adopted':
    case 'relationship_formed':
    case 'pregnancy_detected':
    case 'radio_new_dweller':
    case 'map_registration_failed':
      return dwellerId ? `${vaultPath}/dwellers/${dwellerId}` : `${vaultPath}/dwellers`
    case 'combat_started':
    case 'combat_victory':
    case 'combat_defeat':
    case 'arena_morale_boost': {
      const roomId = metadataString(notification, 'room_id')
      return roomId ? `${vaultPath}?roomId=${encodeURIComponent(roomId)}` : vaultPath
    }
    case 'radio_auto_switched_to_happiness':
      return vaultPath
    case 'location_cleared':
    case 'location_ready': {
      const locationId = metadataString(notification, 'location_id')
      return locationId
        ? `${vaultPath}/map?place=${encodeURIComponent(locationId)}`
        : `${vaultPath}/map`
    }
    case 'objectives_refreshed':
    case 'objective_completed':
    case 'achievement_unlocked':
      return `${vaultPath}/objectives`
    default:
      return vaultPath
  }
}
