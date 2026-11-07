import type { UserProfile } from './profile'

export const SETUP_PREFERENCE_VERSION = 1 as const

export interface SetupPreference {
  version: typeof SETUP_PREFERENCE_VERSION
  completed: boolean
  skipped: boolean
}

type ProfilePreferences = UserProfile['preferences']

/**
 * Read the account-level first-run setup flag from profile preferences.
 * Missing, older or malformed records are treated as not completed so the
 * setup can safely appear again instead of being skipped permanently.
 */
export function parseSetupPreference(raw: unknown): SetupPreference | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const record = raw as Record<string, unknown>
  if (record.version !== SETUP_PREFERENCE_VERSION || typeof record.completed !== 'boolean') {
    return null
  }
  if (record.skipped !== undefined && typeof record.skipped !== 'boolean') return null
  return {
    version: SETUP_PREFERENCE_VERSION,
    completed: record.completed,
    skipped: record.skipped === true,
  }
}

export function isSetupComplete(preferences: ProfilePreferences): boolean {
  return parseSetupPreference(preferences?.setup)?.completed === true
}
