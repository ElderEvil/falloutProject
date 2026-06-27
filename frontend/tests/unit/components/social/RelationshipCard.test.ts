import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RelationshipCard from '@/modules/social/components/relationships/RelationshipCard.vue'

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

function createWrapper(relationship: Record<string, unknown>) {
  return mount(RelationshipCard, {
    props: {
      relationship,
      dweller1Name: 'Alice',
      dweller2Name: 'Bob',
    },
    global: {
      stubs: {
        UButton: {
          template: '<button class="ubutton-stub"><slot /></button>',
          props: ['color', 'size'],
        },
      },
    },
  })
}

describe('RelationshipCard', () => {
  describe('badge class per relationship type', () => {
    it.each([
      { type: 'acquaintance', expectRose: false, expectRed: false, expectAmber: false, expectGray: false },
      { type: 'friend', expectRose: false, expectRed: false, expectAmber: true, expectGray: false },
      { type: 'romantic', expectRose: true, expectRed: false, expectAmber: false, expectGray: false },
      { type: 'partner', expectRose: false, expectRed: true, expectAmber: false, expectGray: false },
      { type: 'ex', expectRose: false, expectRed: false, expectAmber: false, expectGray: true },
    ])('$type badge should have correct color classes', async ({ type, expectRose, expectRed, expectAmber, expectGray }) => {
      const wrapper = createWrapper({
        id: '1',
        dweller_1_id: 'd1',
        dweller_2_id: 'd2',
        relationship_type: type,
        affinity: 50,
      })

      const badge = wrapper.find('span.mt-1')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe(type)

      if (expectRose) {
        expect(badge.classes().some(c => c.includes('rose'))).toBe(true)
      }
      if (expectRed) {
        expect(badge.classes().some(c => c.includes('red'))).toBe(true)
      }
      if (expectAmber) {
        expect(badge.classes().some(c => c.includes('amber'))).toBe(true)
      }
      if (expectGray) {
        expect(badge.classes().some(c => c.includes('gray'))).toBe(true)
      }

      // None should accidentally have another type's color
      if (!expectRose) expect(badge.classes().some(c => c.includes('rose'))).toBe(false)
      if (!expectRed) expect(badge.classes().some(c => c.includes('red'))).toBe(false)
    })

    it('defaults to theme-primary classes for unknown type', () => {
      const wrapper = createWrapper({
        id: '1',
        dweller_1_id: 'd1',
        dweller_2_id: 'd2',
        relationship_type: 'unknown_type',
        affinity: 50,
      })

      const badge = wrapper.find('span.mt-1')
      expect(badge.classes()).toContain('text-theme-primary')
      expect(badge.classes()).toContain('border-theme-primary/30')
    })
  })
})
