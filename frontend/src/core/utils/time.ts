// Shared, side-effect-free time formatting/parsing primitives.
// Each function reproduces an existing call-site behavior so components can
// depend on one implementation instead of re-deriving the same strings.

/** Parse a backend timestamp (naive-UTC or ISO) into epoch milliseconds. */
export function parseUtcMs(input: string): number {
  const normalized = input.includes('T') ? input : input.replace(' ', 'T')
  const withZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`
  return new Date(withZone).getTime()
}

export interface FormatDurationOptions {
  /** Include a seconds branch for sub-hour values (truncated). */
  includeSeconds?: boolean
  /** Drop the `0h` segment for sub-hour values (training/quest "Nm left"). */
  omitZeroHours?: boolean
  /** Truncate (default) or round minute values. */
  rounding?: 'floor' | 'round'
  /** Text appended after the duration, e.g. "remaining" / "left". */
  suffix?: string
}

/**
 * Format a duration in seconds.
 * - default: truncated `Xh Ym` (GameControlPanel game time)
 * - `omitZeroHours`: `Xh Ym` above an hour, else `Ym` (training/quest)
 * - `includeSeconds`: truncated `Xh Ym` / `Ym Zs` / `Zs` (pregnancy/training)
 * - `rounding: 'round'`: rounded `Xh Ym` / `Xh` / `Ym` (crafting timers)
 */
export function formatDuration(
  totalSeconds: number,
  opts: FormatDurationOptions = {}
): string {
  const { includeSeconds = false, omitZeroHours = false, rounding = 'floor', suffix } = opts

  let label: string
  if (rounding === 'round') {
    if (totalSeconds >= 3600) {
      const hours = Math.floor(totalSeconds / 3600)
      const minutes = Math.round((totalSeconds % 3600) / 60)
      label = minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`
    } else {
      label = `${Math.max(1, Math.round(totalSeconds / 60))}m`
    }
  } else if (includeSeconds) {
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = Math.floor(totalSeconds % 60)
    if (hours > 0) label = `${hours}h ${minutes}m`
    else if (minutes > 0) label = `${minutes}m ${seconds}s`
    else label = `${seconds}s`
  } else {
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    label = omitZeroHours && hours === 0 ? `${minutes}m` : `${hours}h ${minutes}m`
  }

  return suffix ? `${label} ${suffix}` : label
}

/** Truncated hours/minutes with a trailing "remaining" (exploration/training). */
export function formatRemaining(seconds: number): string {
  return formatDuration(seconds, { omitZeroHours: true, suffix: 'remaining' })
}

export interface FormatClockOptions {
  /** Pad minutes to two digits (IncidentAlert `MM:SS` style). */
  padMinutes?: boolean
  /** Always render hours as `HH:MM:SS` (quest countdown). */
  showHours?: boolean
}

/**
 * Format a duration as a clock/stopwatch string.
 * - default: `m:ss` with unpadded minutes (audio recording)
 * - `padMinutes`: `MM:SS` with padded minutes, no hours (incident elapsed time)
 * - `showHours`: `HH:MM:SS` with hours and minutes padded (quest countdown)
 */
export function formatClock(
  totalSeconds: number,
  opts: FormatClockOptions = {}
): string {
  const { padMinutes = false, showHours = false } = opts
  const total = Math.max(0, Math.floor(totalSeconds))
  const pad2 = (value: number) => String(value).padStart(2, '0')

  if (showHours) {
    const hours = Math.floor(total / 3600)
    const minutes = Math.floor((total % 3600) / 60)
    return `${pad2(hours)}:${pad2(minutes)}:${pad2(total % 60)}`
  }

  const minutes = Math.floor(total / 60)
  return `${padMinutes ? pad2(minutes) : minutes}:${pad2(total % 60)}`
}

/** Relative "ago" label over a UTC timestamp (notification bell). */
export function formatRelativeTime(isoUtc: string, nowMs: number = Date.now()): string {
  const diff = nowMs - parseUtcMs(isoUtc)
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days > 0) return `${days}d ago`
  if (hours > 0) return `${hours}h ago`
  if (minutes > 0) return `${minutes}m ago`
  return 'Just now'
}

/** Pluralized days-remaining label (dead dweller decay timer). */
export function formatDaysRemaining(days: number): string {
  return `${days} day${days !== 1 ? 's' : ''} remaining`
}

/** Whole seconds until an end timestamp, clamped to zero. */
export function computeRemainingSeconds(endIso: string, nowMs: number): number {
  return Math.max(0, Math.round((parseUtcMs(endIso) - nowMs) / 1000))
}
