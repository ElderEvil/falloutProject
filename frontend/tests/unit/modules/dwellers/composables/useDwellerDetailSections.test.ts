import { describe, expect, it } from 'vite-plus/test'
import { dwellerDetailSections } from '@/modules/dwellers/composables/useDwellerDetailSections'

describe('dwellerDetailSections', () => {
  it('contains the five available detail sections', () => {
    // Collectibles are not a section of their own: they render inside Equipment, where a
    // permanent find sits beside the weapon, outfit and pet the dweller also keeps.
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
