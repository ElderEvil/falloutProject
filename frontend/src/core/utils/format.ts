/**
 * Cross-cutting display formatting. Each helper mirrors the exact output of the
 * ad-hoc call site it replaced (same locale/options), so consolidating a string
 * or date format here never changes a rendered value.
 */

/** Title-case every underscore-separated word, lowercasing the rest ("rare_outfit" → "Rare Outfit"). */
export function humanize(value: string | null | undefined): string {
  if (!value) return ''
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

/** Like {@link humanize} but keeps the original casing after each first letter ("NCR" → "NCR"). */
export function humanizePreserveCase(value: string | null | undefined): string {
  if (!value) return ''
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/** Upper-case only the first character, leaving the rest untouched ("daily" → "Daily"). */
export function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

/** Upper-case incident label ("raider_attack" → "RAIDER ATTACK"). */
export function threatName(type: string): string {
  return humanize(type).toUpperCase()
}

type DateInput = string | number | Date

function toDate(value: DateInput): Date {
  return value instanceof Date ? value : new Date(value)
}

/** Runtime-locale date and time, mirroring `.toLocaleString()`. */
export function formatDateTime(value: DateInput): string {
  return toDate(value).toLocaleString()
}

/** Runtime-locale date only, mirroring `.toLocaleDateString()`. */
export function formatDate(value: DateInput): string {
  return toDate(value).toLocaleDateString()
}

/** Long month and day without a year ("February 1"). */
export function formatMonthDay(value: DateInput): string {
  return toDate(value).toLocaleDateString('en-US', { month: 'long', day: 'numeric' })
}

/** Abbreviated month, day and year from a `YYYY-MM-DD` string, read as local time ("Feb 1, 2026"). */
export function formatShortDate(dateOnly: string): string {
  const [year, month, day] = dateOnly.split('-')
  const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day))
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/** Long month, day and time in en-US ("January 2, 2026 at 03:04 PM"). */
export function formatLongDateTime(value: DateInput): string {
  return toDate(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface ClockOptions {
  /** Emit the leading hours segment, disable for an `mm:ss` clock ("01:30" → "90:00"). */
  padMinutes?: boolean
  showHours?: boolean
  /** Emit the trailing seconds segment, disable for an `hh:mm` clock. */
  showSeconds?: boolean
}

/** Zero-padded clock from a whole-second count, defaulting to `hh:mm:ss`. */
export function formatClock(totalSeconds: number, options: ClockOptions = {}): string {
  const { showHours = true, showSeconds = true, padMinutes = true } = options
  const seconds = Math.floor(totalSeconds)
  const minutes = showHours ? Math.floor((seconds % 3600) / 60) : Math.floor(seconds / 60)
  const segments = [
    ...(showHours ? [String(Math.floor(seconds / 3600)).padStart(2, '0')] : []),
    padMinutes ? String(minutes).padStart(2, '0') : String(minutes),
    ...(showSeconds ? [String(seconds % 60).padStart(2, '0')] : []),
  ]
  return segments.join(':')
}
