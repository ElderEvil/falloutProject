import type { SiteAvailabilityView } from '../api/expeditionSite'

export type SiteAvailabilityReason = SiteAvailabilityView['reason']

const DETAIL: Record<SiteAvailabilityReason, string> = {
  available: 'An expedition site is available on this trail.',
  dead: 'This dweller did not survive the wasteland.',
  catalog_empty: 'No expedition sites are configured for this world.',
  level: 'No sites are unlocked at this dweller’s level yet.',
  trail: 'No sites on this trail yet — keep exploring; sites appear as the trail grows.',
  consumed: 'No new sites are available on this trail.',
  cooldown: 'Recently searched sites are still recovering. Try again later.',
  open: 'A site run is already in progress.',
  unavailable: 'No sites are available right now.',
}

export function siteAvailabilityDetail(reason?: SiteAvailabilityReason | null): string {
  return reason ? DETAIL[reason] : DETAIL.unavailable
}
