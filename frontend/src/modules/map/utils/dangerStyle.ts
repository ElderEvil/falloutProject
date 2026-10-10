export type DangerLevel = 'low' | 'medium' | 'high' | 'unknown'

export interface DangerStyle {
  level: DangerLevel
  /** MapMarker class that ramps the marker ring and glow for this level. */
  className: string
}

export interface DangerLegendEntry {
  level: Exclude<DangerLevel, 'unknown'>
  label: string
}

/** Legend order for the danger ramp; unknown places use the neutral theme colour. */
export const DANGER_RAMP: readonly DangerLegendEntry[] = [
  { level: 'low', label: 'Low risk' },
  { level: 'medium', label: 'Medium risk' },
  { level: 'high', label: 'High risk' },
]

const KNOWN_RISKS = new Set<string>(DANGER_RAMP.map((entry) => entry.level))

function difficultyLevel(difficulty?: number | null): DangerLevel {
  if (typeof difficulty !== 'number' || !Number.isFinite(difficulty) || difficulty <= 0) {
    return 'unknown'
  }
  if (difficulty >= 4) return 'high'
  if (difficulty >= 3) return 'medium'
  return 'low'
}

/**
 * Map a catalog `risk` string to the marker's danger ring/glow class. An
 * unrecognized or missing risk falls back to the `base_difficulty` band, then
 * to the neutral `unknown` level, so no place renders with another's colour.
 */
export function riskToDangerStyle(
  risk?: string | null,
  baseDifficulty?: number | null
): DangerStyle {
  const normalized = typeof risk === 'string' ? risk.trim().toLowerCase() : ''
  const level: DangerLevel = KNOWN_RISKS.has(normalized)
    ? (normalized as DangerLevel)
    : difficultyLevel(baseDifficulty)
  return { level, className: `marker-risk-${level}` }
}
