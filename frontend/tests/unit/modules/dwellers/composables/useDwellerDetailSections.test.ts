import { describe, expect, it } from 'vitest'
import { dwellerDetailSections } from '@/modules/dwellers/composables/useDwellerDetailSections'

describe('dwellerDetailSections', () => {
  it('contains the five available detail sections', () => {
    expect(dwellerDetailSections.map((section) => section.key)).toEqual([
      'profile',
      'appearance',
      'stats',
      'equipment',
      'family',
    ])
  })

  it('defines a label and component for every section', () => {
    dwellerDetailSections.forEach((section) => {
      expect(section.label).toBeTypeOf('string')
      expect(section.component).toBeDefined()
    })
  })
})
