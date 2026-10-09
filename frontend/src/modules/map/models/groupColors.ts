/**
 * Optional per-group marker colors for the "group identity" color mode.
 *
 * EXPERIMENT (dev mockup, `/dev/map-mockup`): when enabled, a known marker's
 * glyph is tinted by its place group instead of the single state color. State
 * still owns the semantics that must not be lost — unknown/locked stays grey,
 * cleared stays dimmed, vault/explorer keep their own hues — so group color only
 * replaces the base "known" tint.
 *
 * Palette chosen by perceptual separation (CIE76 dE): the closest pair is ~20
 * and every entry is >= 20 from the locked-grey token and far from the theme
 * green. Hues are assigned to fit each group's meaning (red = fuel, amber =
 * power, violet = research, olive = military, teal = transit, ...).
 *
 * Frontend-only for now. If adopted, move this palette into
 * `backend/app/data/places/place_groups.json` as a `color` field per group so it
 * becomes data-driven and themeable like the rest of the catalog.
 */
export const GROUP_COLORS: Record<string, string> = {
  settlement: '#b57a3a',
  city: '#4f86d6',
  gas_station: '#e04b45',
  supermarket: '#a9d94b',
  factory: '#6f8494',
  metro: '#2fb3a8',
  military: '#7d8f3f',
  brotherhood_outpost: '#5f6fa0',
  research: '#b06fd6',
  power: '#ffd60a',
  entertainment: '#e86fb0',
  landmark: '#d9b53a',
  vault_tec: '#3556c9',
  ruin: '#8a5a3b',
  region: '#5fae6a',
  exclusion_zone: '#d96f26',
  wasteland_site: '#bcc4a8',
}

/** Color for a place-group key, or undefined for ungrouped/unknown keys. */
export function groupColor(key: string | null | undefined): string | undefined {
  return key ? GROUP_COLORS[key] : undefined
}
