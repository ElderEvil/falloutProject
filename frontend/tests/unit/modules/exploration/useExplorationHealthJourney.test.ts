import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import { useExplorationHealthJourney } from '@/modules/exploration/composables/useExplorationHealthJourney'

describe('useExplorationHealthJourney', () => {
  it('combines structured health data with legacy health descriptions into a trend', () => {
    const events = ref([
      {
        type: 'danger',
        description: 'Encountered toxic waste. Health reduced by 7.',
        timestamp: '2026-01-01T00:00:00Z',
        time_elapsed_hours: 1,
      },
      {
        type: 'item_use',
        description: 'Used a stimpak. Healed 5 health.',
        timestamp: '2026-01-01T00:30:00Z',
        time_elapsed_hours: 1.5,
      },
      {
        type: 'combat',
        description: 'A raider attacked.',
        timestamp: '2026-01-01T01:00:00Z',
        time_elapsed_hours: 2,
        health_loss: 3,
      },
    ])

    const { healthJourney, totalDamage, totalHealed, healthTrendPoints } = useExplorationHealthJourney(events)

    expect(healthJourney.value).toHaveLength(3)
    expect(totalDamage.value).toBe(10)
    expect(totalHealed.value).toBe(5)
    expect(healthTrendPoints.value).toMatch(/^0\.0,.* 40\.0,.* 80\.0,.* 120\.0,/)
  })
})
