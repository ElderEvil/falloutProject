import type { WastelandLocationWithDwellers } from './map'

export type MarkerType =
  | WastelandLocationWithDwellers['type']
  | 'vault'
  | 'expedition_site'
  | 'explorer'

export interface MarkerTypeMeta {
  type: MarkerType
  icon: string
  label: string
}

// Single shared icon for expedition sites: the map, legend and list panel all
// render the same star marker regardless of the site's name.
export const EXPEDITION_SITE_ICON = 'mdi:map-marker-star'

export const MARKER_TYPES: readonly MarkerTypeMeta[] = [
  { type: 'home_vault', icon: 'mdi:home-city', label: 'Home Vault' },
  { type: 'origin', icon: 'mdi:flag', label: 'Origin' },
  { type: 'visited', icon: 'mdi:eye', label: 'Visited' },
  { type: 'discovery', icon: 'mdi:map-marker-question', label: 'Discovery' },
  { type: 'vault', icon: 'mdi:radioactive', label: 'Vault Signal' },
  { type: 'expedition_site', icon: EXPEDITION_SITE_ICON, label: 'Expedition Sites' },
]

const BY_TYPE = new Map<string, MarkerTypeMeta>(MARKER_TYPES.map((meta) => [meta.type, meta]))

export function markerTypeMeta(type: string): MarkerTypeMeta {
  return BY_TYPE.get(type) ?? { type: type as MarkerType, icon: 'mdi:map-marker', label: type }
}

/**
 * Marker icon for a wasteland location: its site-type archetype icon when the
 * catalog has one, else the generic type icon. Keeps map markers consistent with
 * the legend and list panel, which already render archetype icons.
 */
export function locationMarkerIcon(
  type: string,
  groupKey: string | null | undefined,
  groupIconByKey: ReadonlyMap<string, string>,
): string {
  if (groupKey) {
    const groupIcon = groupIconByKey.get(groupKey)
    if (groupIcon) return groupIcon
  }
  return markerTypeMeta(type).icon
}
