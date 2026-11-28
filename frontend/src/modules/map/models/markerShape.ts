import type { WastelandLocationWithDwellers } from './map'

/**
 * What a place is *for*. The marker body shape is the map's primary axis: a
 * player reads "raid this / trade here / just look" before decoding the site
 * archetype glyph inside.
 */
export type PlacePurpose = 'clear' | 'trade' | 'look' | 'home'

/**
 * The silhouettes a marker body can take. Four purposes need four shapes the eye
 * can tell apart both at 4.2 user units and at the legend's 12px swatch: a filled
 * circle, a diamond, a hollow triangle and a rounded square. The Look shape stays
 * hollow — the fill is what separates it from the circle at swatch size, so the
 * silhouette must never be filled in.
 *
 * A shape means purpose and nothing else. It is never swapped to signal state:
 * approached, selected and exploring markers keep their silhouette and announce
 * themselves with an animated ring (see `marker-select-ping`).
 */
export type MarkerShape = 'circle' | 'diamond' | 'triangle' | 'square'

export interface PurposeMeta {
  purpose: PlacePurpose
  shape: MarkerShape
  label: string
  /** One line, never a paragraph: the legend has to stay readable. */
  hint: string
}

export const PURPOSE_META: readonly PurposeMeta[] = [
  { purpose: 'clear', shape: 'circle', label: 'Clear', hint: 'raid · salvage' },
  { purpose: 'trade', shape: 'diamond', label: 'Trade', hint: 'caravan' },
  { purpose: 'look', shape: 'triangle', label: 'Look', hint: 'landmark' },
  { purpose: 'home', shape: 'square', label: 'Home', hint: 'your vault' },
]

const BY_SHAPE = new Map<MarkerShape, PurposeMeta>(PURPOSE_META.map((meta) => [meta.shape, meta]))

/** Legend metadata for a body shape; an unknown shape reads as Look, never a raid. */
export function shapeMeta(shape: MarkerShape | null | undefined): PurposeMeta {
  return BY_SHAPE.get(shape ?? 'triangle') ?? BY_SHAPE.get('triangle')!
}

/** Groups that trade but are not clearable; the API's `action` already says so. */
const TRADE_GROUPS = new Set(['settlement', 'city'])

type ShapeSource = Pick<WastelandLocationWithDwellers, 'type' | 'action'> & {
  group_key?: string | null
}

/**
 * Resolve the body shape a location draws. `action` is authoritative — the
 * backend already computes `clear | salvage | trade | none` per place — with the
 * group key as a fallback for payloads that predate it. Salvage folds into Clear:
 * it is the same trip shape, only the copy differs.
 */
export function shapeFor(location: ShapeSource | null | undefined): MarkerShape {
  if (!location) return 'triangle'
  if (location.type === 'home_vault') return 'square'

  switch (location.action) {
    case 'clear':
    case 'salvage':
      return 'circle'
    case 'trade':
      return 'diamond'
    case 'none':
      return 'triangle'
  }

  if (location.group_key && TRADE_GROUPS.has(location.group_key)) return 'diamond'
  return 'triangle'
}
