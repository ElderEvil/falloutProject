import type { WastelandLocationWithDwellers } from './map'

export type PlacePurpose = 'clear' | 'trade' | 'look' | 'home'

export type MarkerShape = 'circle' | 'diamond' | 'hexagon' | 'square'

export interface PurposeMeta {
  purpose: PlacePurpose
  shape: MarkerShape
  label: string
  hint: string
}

export const PURPOSE_META: readonly PurposeMeta[] = [
  { purpose: 'clear', shape: 'circle', label: 'Clear', hint: 'raid' },
  { purpose: 'trade', shape: 'diamond', label: 'Trade', hint: 'caravan' },
  { purpose: 'look', shape: 'square', label: 'Look', hint: 'landmark' },
  { purpose: 'home', shape: 'hexagon', label: 'Home', hint: 'your vault' },
]

const BY_SHAPE = new Map<MarkerShape, PurposeMeta>(PURPOSE_META.map((meta) => [meta.shape, meta]))
const SHAPE_BY_PURPOSE = new Map<PlacePurpose, MarkerShape>(
  PURPOSE_META.map((meta) => [meta.purpose, meta.shape])
)
const LOOK_SHAPE = SHAPE_BY_PURPOSE.get('look')!
const HOME_SHAPE = SHAPE_BY_PURPOSE.get('home')!

/** Legend metadata for a body shape; an unknown shape reads as Look, never a raid. */
export function shapeMeta(shape: MarkerShape | null | undefined): PurposeMeta {
  return BY_SHAPE.get(shape ?? LOOK_SHAPE) ?? BY_SHAPE.get(LOOK_SHAPE)!
}

const TRADE_GROUPS = new Set(['settlement', 'city'])

type ShapeSource = Pick<WastelandLocationWithDwellers, 'type' | 'group_key'> & {
  purpose?: string | null
}

// Static purpose wins; the group fallback only covers older payloads. Never read `action` here.
export function shapeFor(location: ShapeSource | null | undefined): MarkerShape {
  if (!location) return LOOK_SHAPE
  if (location.type === 'home_vault') return HOME_SHAPE
  const shape = location.purpose
    ? SHAPE_BY_PURPOSE.get(location.purpose as PlacePurpose)
    : undefined
  if (shape) return shape
  return location.group_key && TRADE_GROUPS.has(location.group_key) ? 'diamond' : LOOK_SHAPE
}
