import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import type { ExplorationEvent } from '@/modules/exploration/stores/exploration'

function toTrendPoints(values: number[]): string {
  const min = Math.min(...values)
  const range = Math.max(...values) - min || 1
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * 120
      const y = 28 - ((value - min) / range) * 28
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

export function useExplorationHealthJourney(
  events: MaybeRefOrGetter<ExplorationEvent[] | null | undefined>
) {
  const healthJourney = computed(() =>
    (toValue(events) ?? [])
      .map((event) => {
        const damage = event.description.match(/(?:health reduced by|took)\s+(\d+)(?:\s+(?:damage|hp))?/i)
        const healing = event.description.match(/(?:healed|restored)\s+(\d+)(?:\s+(?:health|hp))?/i)

        return {
          ...event,
          health_loss: event.health_loss ?? (damage ? Number.parseInt(damage[1]!, 10) : undefined),
          health_restored: event.health_restored ?? (healing ? Number.parseInt(healing[1]!, 10) : undefined),
        }
      })
      .filter((event) => event.health_loss != null || event.health_restored != null)
  )
  const totalDamage = computed(() => healthJourney.value.reduce((sum, event) => sum + (event.health_loss ?? 0), 0))
  const totalHealed = computed(() => healthJourney.value.reduce((sum, event) => sum + (event.health_restored ?? 0), 0))
  const healthTrendPoints = computed(() => {
    const values = [0]
    for (const event of healthJourney.value) {
      values.push(values[values.length - 1]! + (event.health_restored ?? 0) - (event.health_loss ?? 0))
    }
    return toTrendPoints(values)
  })

  const radiationJourney = computed(() =>
    (toValue(events) ?? []).filter((event) => event.radiation_gain != null || event.radiation_removed != null)
  )
  const totalRadiationRemoved = computed(() =>
    radiationJourney.value.reduce((sum, event) => sum + (event.radiation_removed ?? 0), 0)
  )
  const radiationTrendPoints = computed(() => {
    const values = [0]
    for (const event of radiationJourney.value) {
      values.push(values[values.length - 1]! + (event.radiation_removed ?? 0) - (event.radiation_gain ?? 0))
    }
    return toTrendPoints(values)
  })

  return {
    healthJourney,
    totalDamage,
    totalHealed,
    healthTrendPoints,
    radiationJourney,
    totalRadiationRemoved,
    radiationTrendPoints,
  }
}
