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
  settlement: 'var(--color-group-settlement)',
  city: 'var(--color-group-city)',
  gas_station: 'var(--color-group-gas_station)',
  supermarket: 'var(--color-group-supermarket)',
  factory: 'var(--color-group-factory)',
  metro: 'var(--color-group-metro)',
  military: 'var(--color-group-military)',
  brotherhood_outpost: 'var(--color-group-brotherhood_outpost)',
  research: 'var(--color-group-research)',
  power: 'var(--color-group-power)',
  entertainment: 'var(--color-group-entertainment)',
  landmark: 'var(--color-group-landmark)',
  vault_tec: 'var(--color-group-vault_tec)',
  ruin: 'var(--color-group-ruin)',
  region: 'var(--color-group-region)',
  exclusion_zone: 'var(--color-group-exclusion_zone)',
  wasteland_site: 'var(--color-group-wasteland_site)',
}

/** Color for a place-group key, or undefined for ungrouped/unknown keys. */
export function groupColor(key: string | null | undefined): string | undefined {
  return key ? GROUP_COLORS[key] : undefined
}
