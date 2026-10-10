/**
 * Discovery-only visibility contract for the production map.
 *
 * Production has no explored-cell fog: a place is "known" once discovery/unlock
 * records it. Unknown places stay visible only as anonymous hints (position shown,
 * identity and actions withheld). This is the single rule for rendering, selection,
 * routing, ETA, and the index — do not re-derive it at call sites.
 */
export interface VisibilityInput {
  type: string
  is_unlocked?: boolean
}

/** Known identity: the home vault (always) or any unlocked location. */
export function isKnownLocation(loc: VisibilityInput): boolean {
  return loc.type === 'home_vault' || loc.is_unlocked !== false
}

/** Shown as an anonymous hint: a place that is not known and not already a signal. */
export function isHintLocation(loc: VisibilityInput): boolean {
  return loc.type !== 'home_vault' && loc.type !== 'vault' && !loc.is_unlocked
}
