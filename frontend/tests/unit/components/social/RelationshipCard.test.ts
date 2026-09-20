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

const dweller1 = {
  id: 'd1',
  first_name: 'Alice',
  last_name: 'Smith',
  level: 5,
  thumbnail_url: null,
  gender: 'female',
}

const dweller2 = {
  id: 'd2',
  first_name: 'Bob',
  last_name: 'Jones',
  level: 7,
  thumbnail_url: null,
  gender: 'male',
}

function createWrapper(relationship: Record<string, unknown>, viewMode?: 'list' | 'grid') {
  return mount(RelationshipCard, {
    props: {
      relationship,
      dweller1,
      dweller2,
      viewMode,
    },
    global: {
      stubs: {
        UButton: {
          template: '<button class="ubutton-stub"><slot /></button>',
          props: ['color', 'size'],
        },
        DwellerPortrait: {
          template: '<span class="dweller-portrait-stub" :data-alt="alt" />',
          props: ['alt'],
        },
        DwellerGenderBadge: {
          template: '<span class="dweller-gender-stub" :data-gender="gender" />',
          props: ['gender', 'size'],
        },
      },
    },
  })
}

describe('RelationshipCard', () => {
  it('uses the compact relationship row by default', () => {
    const wrapper = createWrapper({
      id: '1',
      dweller_1_id: 'd1',
      dweller_2_id: 'd2',
      relationship_type: 'friend',
      affinity: 50,
    })

    expect(wrapper.find('.relationship-record--list').exists()).toBe(true)
  })

  it('renders dweller thumbnails in list mode', () => {
    const wrapper = createWrapper({
      id: '1',
      dweller_1_id: 'd1',
      dweller_2_id: 'd2',
      relationship_type: 'friend',
      affinity: 50,
    })

    const portraits = wrapper.findAll('.dweller-portrait-stub')
    expect(portraits).toHaveLength(2)
    expect(portraits[0].attributes('data-alt')).toBe('Alice Smith')
    expect(portraits[1].attributes('data-alt')).toBe('Bob Jones')
  })

  describe('grid mode identity presentation', () => {
    it('renders portraits, level, and gender badge for both dwellers', () => {
      const wrapper = createWrapper(
        {
          id: '1',
          dweller_1_id: 'd1',
          dweller_2_id: 'd2',
          relationship_type: 'friend',
          affinity: 50,
        },
        'grid'
      )

      expect(wrapper.find('.relationship-record--grid').exists()).toBe(true)

      const portraits = wrapper.findAll('.dweller-portrait-stub')
      expect(portraits).toHaveLength(2)
      expect(portraits[0].attributes('data-alt')).toBe('Alice Smith')
      expect(portraits[1].attributes('data-alt')).toBe('Bob Jones')

      expect(wrapper.text()).toContain('LVL 5')
      expect(wrapper.text()).toContain('LVL 7')

      const genderBadges = wrapper.findAll('.dweller-gender-stub')
      expect(genderBadges).toHaveLength(2)
      expect(genderBadges[0].attributes('data-gender')).toBe('female')
      expect(genderBadges[1].attributes('data-gender')).toBe('male')
    })
  })

  describe('badge variant per relationship type', () => {
    it.each([
      { type: 'acquaintance', expectClass: 'bg-success' },
      { type: 'friend', expectClass: 'bg-warning' },
      { type: 'romantic', expectClass: 'border-2' },
      { type: 'partner', expectClass: 'bg-danger' },
      { type: 'MARRIED', expectClass: 'bg-danger' },
      { type: 'ex', expectClass: 'bg-surface-raised' },
    ])('$type badge should have correct variant class', async ({ type, expectClass }) => {
      const wrapper = createWrapper({
        id: '1',
        dweller_1_id: 'd1',
        dweller_2_id: 'd2',
        relationship_type: type,
        affinity: 50,
      })

      const badge = wrapper.find('.relationship-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe(type)
      expect(badge.classes().includes(expectClass)).toBe(true)
    })

    it('defaults to success variant for unknown type', () => {
      const wrapper = createWrapper({
        id: '1',
        dweller_1_id: 'd1',
        dweller_2_id: 'd2',
        relationship_type: 'unknown_type',
        affinity: 50,
      })

      const badge = wrapper.find('.relationship-badge')
      expect(badge.classes()).toContain('bg-success')
    })
  })

  describe('action buttons per stage', () => {
    it('shows a Marry button for partners at 85+ affinity', () => {
      const wrapper = createWrapper({
        id: '1',
        dweller_1_id: 'd1',
        dweller_2_id: 'd2',
        relationship_type: 'partner',
        affinity: 85,
      })

      expect(wrapper.text()).toContain('Marry')
    })

    it('hides the Marry button for partners below 85 affinity', () => {
      const wrapper = createWrapper({
        id: '1',
        dweller_1_id: 'd1',
        dweller_2_id: 'd2',
        relationship_type: 'partner',
        affinity: 84,
      })

      expect(wrapper.text()).not.toContain('Marry')
    })

    it('shows a Break Up button for married relationships', () => {
      const wrapper = createWrapper({
        id: '1',
        dweller_1_id: 'd1',
        dweller_2_id: 'd2',
        relationship_type: 'MARRIED',
        affinity: 90,
      })

      expect(wrapper.text()).toContain('Break Up')
    })
  })

  it('treats both dwelller identities as direct roster links', async () => {
    const wrapper = createWrapper({
      id: '1',
      dweller_1_id: 'd1',
      dweller_2_id: 'd2',
      relationship_type: 'friend',
      affinity: 50,
    })

    await wrapper.get('button[title="View Alice Smith"]').trigger('click')
    await wrapper.get('button[title="View Bob Jones"]').trigger('click')

    expect(wrapper.emitted('select-dweller')).toEqual([['d1'], ['d2']])
  })
})