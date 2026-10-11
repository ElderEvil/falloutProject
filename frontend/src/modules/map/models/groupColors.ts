/** Optional place-group glyph colours. State uses badges and danger uses text;
 * locked places stay neutral, and ungrouped markers follow the active theme.
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
