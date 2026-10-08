import type { MarkerType } from '../models/markerTypeMeta'

/**
 * Zoom at which secondary markers fade back into the map. Below it the map
 * shows only primary markers, so a hundred anonymous vault signals cannot
 * swamp the overview; zooming in (wheel, pinch, or focusing a marker) reveals
 * the rest.
 */
export const DECLUTTER_REVEAL_ZOOM = 1.5

export interface MarkerDeclutterInput {
  type: MarkerType
  selected?: boolean
  exploring?: boolean
}

/**
 * Primary markers carry live player intent and always render: the home vault
 * (and own vaults), the current selection, discoveries ("discovering"), active
 * explorers and expedition sites, and locations currently being explored.
 * Everything else — origins, visited places and anonymous vault hints — is
 * secondary.
 */
export function isPrimaryMarker(marker: MarkerDeclutterInput): boolean {
  return (
    marker.type === 'home_vault' ||
    marker.type === 'discovery' ||
    marker.type === 'explorer' ||
    marker.type === 'expedition_site' ||
    marker.selected === true ||
    marker.exploring === true
  )
}

/** Secondary markers stay hidden until the map is zoomed past the threshold. */
export function isMarkerVisible(marker: MarkerDeclutterInput, zoom: number): boolean {
  return isPrimaryMarker(marker) || zoom >= DECLUTTER_REVEAL_ZOOM
}
