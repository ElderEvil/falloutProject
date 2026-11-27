import type { WastelandLocationWithDwellers } from './map'

/**
 * What a place is *for*. Purpose is the map's primary axis: the marker's body
 * shape encodes it, so a player reads "raid this / trade here / just look"
 * before ever decoding the site archetype glyph inside.
 */
export type PlacePurpose = 'clear' | 'trade' | 'look' | 'home'

export interface PurposeMeta {
  purpose: PlacePurpose
  label: string
  /** One line, never a paragraph: the legend has to stay readable. */
  hint: string
  shape: 'circle' | 'diamond' | 'ring' | 'square'
}

export const PURPOSE_META: readonly PurposeMeta[] = [
  { purpose: 'clear', label: 'Clear', hint: 'raid · salvage', shape: 'circle' },
  { purpose: 'trade', label: 'Trade', hint: 'caravan', shape: 'diamond' },
  { purpose: 'look', label: 'Look', hint: 'landmark', shape: 'ring' },
  { purpose: 'home', label: 'Home', hint: 'your vault', shape: 'square' },
]

const BY_PURPOSE = new Map<PlacePurpose, PurposeMeta>(
  PURPOSE_META.map((meta) => [meta.purpose, meta])
)

export function purposeMeta(purpose: PlacePurpose | null | undefined): PurposeMeta {
  return BY_PURPOSE.get(purpose ?? 'look') ?? BY_PURPOSE.get('look')!
}

/** Groups that trade but are not clearable; the API's `action` already says so. */
const TRADE_GROUPS = new Set(['settlement', 'city'])

type PurposeSource = Pick<WastelandLocationWithDwellers, 'type' | 'action'> & {
  group_key?: string | null
}

/**
 * Resolve a location's purpose. `action` is authoritative — the backend already
 * computes `clear | salvage | trade | none` per place — with the group key as a
 * fallback for payloads that predate it. Salvage folds into Clear: it is the
 * same trip shape, only the copy differs.
 */
export function purposeFor(location: PurposeSource | null | undefined): PlacePurpose {
  if (!location) return 'look'
  if (location.type === 'home_vault') return 'home'

  switch (location.action) {
    case 'clear':
    case 'salvage':
      return 'clear'
    case 'trade':
      return 'trade'
    case 'none':
      return 'look'
  }

  if (location.group_key && TRADE_GROUPS.has(location.group_key)) return 'trade'
  return 'look'
}
