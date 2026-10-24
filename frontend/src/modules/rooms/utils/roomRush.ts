import type { RoomRushResourceGain, RoomRushResult } from '../models/room'

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

export function formatRushResult(result: RoomRushResult): string {
  if (result.outcome === 'failure') {
    const [incident] = rushConsequenceTags(result.incident_type ? [result.incident_type] : [])
    const parts = [incident]
    if (result.happiness_delta !== 0) {
      const delta = result.happiness_delta
      parts.push(`${delta > 0 ? '+' : '−'}${Math.abs(delta)} HAPPINESS`)
    }
    return parts.join(' · ')
  }

  const gains = (Object.entries(result.payout) as [keyof RoomRushResourceGain, number][])
    .filter(([, amount]) => amount > 0)
    .map(([key, amount]) => `+${amount} ${PAYOUT_LABELS[key].toUpperCase()}`)
  if (result.caps > 0) gains.push(`+${result.caps} CAPS`)
  if (result.happiness_delta !== 0) {
    const delta = result.happiness_delta
    gains.push(`${delta > 0 ? '+' : '−'}${Math.abs(delta)} HAPPINESS`)
  }
  const xp = result.xp_per_worker > 0 ? `+${result.xp_per_worker} XP` : ''
  if (gains.length === 0)
    return xp ? `No resources (at capacity) · ${xp}` : 'No resources (at capacity)'
  if (xp) gains.push(xp)
  return gains.join(' · ')
}
