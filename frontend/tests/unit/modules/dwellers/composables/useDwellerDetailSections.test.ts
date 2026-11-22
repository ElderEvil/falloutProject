import { describe, expect, it } from 'vite-plus/test'
import { dwellerDetailSections } from '@/modules/dwellers/composables/useDwellerDetailSections'

describe('dwellerDetailSections', () => {
  it('contains the six available detail sections', () => {
    expect(dwellerDetailSections.map((section) => section.key)).toEqual([
      'profile',
      'appearance',
      'stats',
      'equipment',
      'collectibles',
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
