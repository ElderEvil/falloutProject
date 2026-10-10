import type { WastelandLocationWithDwellers } from '../models/map'

/**
 * P3 site-type filter predicate, shared by the map and the marker index so both
 * surfaces narrow identically: a place of the chosen archetype, plus the home
 * vault (never a site type). A null filter matches every location.
 */
export function matchesSiteTypeFilter(
  loc: Pick<WastelandLocationWithDwellers, 'type' | 'group_key'>,
  filter: string | null
): boolean {
  return filter === null || loc.type === 'home_vault' || loc.group_key === filter
}
