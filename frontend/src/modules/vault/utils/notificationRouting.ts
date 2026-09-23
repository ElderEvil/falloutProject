export interface NotificationNavigationContext {
  vault_id?: string | null
  from_dweller_id?: string | null
  notification_type: string
  meta_data?: Record<string, unknown> | null
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
    case 'relationship_formed':
    case 'pregnancy_detected':
    case 'radio_new_dweller':
    case 'map_registration_failed':
      return dwellerId ? `${vaultPath}/dwellers/${dwellerId}` : `${vaultPath}/dwellers`
    case 'combat_started':
    case 'combat_victory':
    case 'combat_defeat': {
      const roomId = metadataString(notification, 'room_id')
      return roomId ? `${vaultPath}?roomId=${encodeURIComponent(roomId)}` : vaultPath
    }
    case 'radio_auto_switched_to_happiness':
      return vaultPath
    case 'achievement_unlocked':
      return `${vaultPath}/objectives`
    default:
      return vaultPath
  }
}
