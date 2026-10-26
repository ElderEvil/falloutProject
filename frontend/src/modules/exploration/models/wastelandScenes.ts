import scenes from './wasteland-scenes.json'

export type WastelandSceneId = keyof typeof scenes
export type WastelandSceneRole = 'landscape' | 'battleback'
export const WASTELAND_SCENES = scenes

/** Artwork describes the last reported location; it never invents a new destination. */
export function getLocationScene(name: string | null | undefined): WastelandSceneId | null {
  if (!name) return null
  if (/\b(arctic|polar|frozen|anchorage)\b/i.test(name)) return 'arctic_research_station'
  if (/\b(supermarket|super duper mart|super-duper mart)\b/i.test(name))
    return 'supermarket_interior'
  if (/\b(subway|metro)\b/i.test(name)) return 'subway_station'
  if (/\b(amusement park|nuka.world|fairgrounds|carnival)\b/i.test(name)) return 'amusement_park'
  if (/\b(highway|roadside|supply truck)\b/i.test(name)) return 'desert_highway'
  return null
}

export function getSiteScene(siteId: string, roomName?: string): WastelandSceneId | null {
  if (siteId === 'super_duper_mart')
    return roomName === 'Parking Lot' ? 'desert_highway' : 'supermarket_interior'
  if (siteId === 'roadside_supply_truck') return 'desert_highway'
  return null
}
