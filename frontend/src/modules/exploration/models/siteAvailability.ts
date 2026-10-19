import type { SiteAvailabilityView } from '../api/expeditionSite'

export type SiteAvailabilityReason = SiteAvailabilityView['reason']

const DETAIL: Record<SiteAvailabilityReason, string> = {
  available: 'An expedition site is nearby.',
  dead: 'This dweller did not survive the wasteland.',
  catalog_empty: 'No expedition sites are configured for this world.',
  level: 'No sites are unlocked at this dweller’s level yet.',
  trail: 'No sites lie near this trail — travel further to find one.',
  consumed: 'Every site on this trail has already been searched.',
  cooldown: 'Recently searched sites are still recovering. Try again later.',
  open: 'A site run is already in progress.',
  unavailable: 'No sites are available right now.',
}

const SHORT: Record<SiteAvailabilityReason, string> = {
  available: 'Site nearby',
  dead: 'Dweller lost',
  catalog_empty: 'No sites configured',
  level: 'Level too low for sites',
  trail: 'No sites on this trail',
  consumed: 'Trail searched',
  cooldown: 'Sites recovering',
  open: 'Site run in progress',
  unavailable: 'No sites available',
}

export function siteAvailabilityDetail(reason?: SiteAvailabilityReason | null): string {
  return reason ? DETAIL[reason] : 'No sites are available right now.'
}

export function siteAvailabilityShort(reason?: SiteAvailabilityReason | null): string {
  return reason ? SHORT[reason] : SHORT.unavailable
}
