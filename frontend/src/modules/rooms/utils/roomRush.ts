import type { RoomRushResourceGain } from '../models/room'

const CONSEQUENCE_TAGS: Record<string, string> = {
  fire: 'FIRE',
  radroach_infestation: 'RADROACH',
  mole_rat_attack: 'MOLE RAT',
  radscorpion_attack: 'RADSCORPION',
}

export function rushConsequenceTags(incidents: string[]): string[] {
  if (incidents.length === 0) return ['NO INCIDENT']
  return incidents.map(
    (incident) => CONSEQUENCE_TAGS[incident] ?? incident.replaceAll('_', ' ').toUpperCase()
  )
}

const PAYOUT_LABELS: Record<keyof RoomRushResourceGain, string> = {
  power: 'Power',
  food: 'Food',
  water: 'Water',
  stimpack: 'Stimpacks',
  radaway: 'RadAway',
}

export function formatRushPayout(payout: RoomRushResourceGain): string {
  const parts = (Object.entries(payout) as [keyof RoomRushResourceGain, number][])
    .filter(([, amount]) => amount > 0)
    .map(([key, amount]) => `+${amount} ${PAYOUT_LABELS[key]}`)
  return parts.length ? parts.join(', ') : 'no resources (at capacity)'
}
