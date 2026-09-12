import type { WastelandLocationWithDwellers } from './map'

export type MarkerType = WastelandLocationWithDwellers['type'] | 'vault'

export interface MarkerTypeMeta {
  type: MarkerType
  icon: string
  label: string
}

export const MARKER_TYPES: readonly MarkerTypeMeta[] = [
  { type: 'home_vault', icon: 'mdi:home-city', label: 'Home Vault' },
  { type: 'origin', icon: 'mdi:flag', label: 'Origin' },
  { type: 'visited', icon: 'mdi:eye', label: 'Visited' },
  { type: 'discovery', icon: 'mdi:compass', label: 'Discovery' },
  { type: 'vault', icon: 'mdi:radioactive', label: 'Vault Signal' },
]

const BY_TYPE = new Map<string, MarkerTypeMeta>(MARKER_TYPES.map((meta) => [meta.type, meta]))

export function markerTypeMeta(type: string): MarkerTypeMeta {
  return BY_TYPE.get(type) ?? { type: type as MarkerType, icon: 'mdi:map-marker', label: type }
}
