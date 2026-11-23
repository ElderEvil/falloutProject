/** Place-type identity colours, grouped into five site families.
 *
 * Nineteen hues is past the point where anyone can decode them, so identity is
 * carried by five families the eye can sort without reading, and the glyph keeps
 * saying which place it is. Identity only — never state: an unscouted place keeps
 * its family tint, dimmed inside a dashed ring.
 */
export const GROUP_FAMILIES = {
  civil: 'var(--color-family-civil)',
  industry: 'var(--color-family-industry)',
  threat: 'var(--color-family-threat)',
  knowledge: 'var(--color-family-knowledge)',
  spectacle: 'var(--color-family-spectacle)',
} as const

export type GroupFamily = keyof typeof GROUP_FAMILIES

/** Every place-group key the catalog ships, mapped to the family it belongs to. */
const FAMILY_BY_GROUP: Record<string, GroupFamily> = {
  // Where people live.
  settlement: 'civil',
  city: 'civil',
  metro: 'civil',
  vertical_refuge: 'civil',
  ruin: 'civil',
  // Where materials come from.
  gas_station: 'industry',
  supermarket: 'industry',
  factory: 'industry',
  power: 'industry',
  // Where you fight.
  military: 'threat',
  brotherhood_outpost: 'threat',
  exclusion_zone: 'threat',
  wasteland_site: 'threat',
  // Where tech comes from.
  research: 'knowledge',
  vault_tec: 'knowledge',
  observation_facility: 'knowledge',
  // Where you look, not loot.
  entertainment: 'spectacle',
  landmark: 'spectacle',
  region: 'spectacle',
}

/** Family for a place-group key, or undefined for ungrouped/unknown keys. */
export function familyFor(key: string | null | undefined): GroupFamily | undefined {
  return key ? FAMILY_BY_GROUP[key] : undefined
}

/** Display names for the five families, in the order the legend lists them. */
export const FAMILY_LABELS: Record<GroupFamily, string> = {
  civil: 'Civil',
  industry: 'Industry',
  threat: 'Threat',
  knowledge: 'Knowledge',
  spectacle: 'Spectacle',
}

/** What each family contains, in plain words, for the map legend. */
export const FAMILY_MEANING: Record<GroupFamily, string> = {
  civil: 'settlements, cities, ruins',
  industry: 'fuel, food, factories, power',
  threat: 'military, raiders, wasteland sites',
  knowledge: 'research, vault tech, observatories',
  spectacle: 'entertainment, landmarks, regions',
}

/** Colour for a place-group key, or undefined for ungrouped/unknown keys. */
export function groupColor(key: string | null | undefined): string | undefined {
  const family = familyFor(key)
  return family ? GROUP_FAMILIES[family] : undefined
}
