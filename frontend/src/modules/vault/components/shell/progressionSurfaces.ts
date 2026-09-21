/**
 * Progression visibility matrix (red line — `docs/backend/GAME_MECHANICS.md`).
 *
 * Every player-facing progression event must surface via modal/pop-up or toast
 * *in addition to* the notification bell entry, never notification-only.
 *
 * This is the single source of truth for which notification types get that
 * extra surface. It deliberately covers only the rule's scope — level-up, loot,
 * training completion, and quest/objective completion — plus the hazard-team
 * join that already surfaced. Informational events (resource warnings, combat
 * updates, exploration chatter) stay bell-only on purpose: adding them would be
 * noise, not progression.
 *
 * A new progression flow must add its type here (with a test), otherwise it
 * ships notification-only.
 */

export type ProgressionSurface = 'toast'

export const PROGRESSION_SURFACES: Readonly<Record<string, ProgressionSurface>> = Object.freeze({
  // level-up
  level_up: 'toast',
  // loot found on an exploration (surfaces even when the user is not in the view)
  exploration_complete: 'toast',
  // training completion
  training_complete: 'toast',
  // quest completion
  quest_complete: 'toast',
  // objective completion (the backend emits objectives as ACHIEVEMENT_UNLOCKED)
  achievement_unlocked: 'toast',
  // roster progression (already surfaced before this module existed)
  hazard_team_joined: 'toast',
})

/** The extra surface a notification type requires, or null for bell-only. */
export function progressionSurfaceFor(notificationType: string): ProgressionSurface | null {
  return PROGRESSION_SURFACES[notificationType] ?? null
}
