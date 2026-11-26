import { describe, it, expect, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import RelationshipCard from '@/modules/social/components/relationships/RelationshipCard.vue'
import { makeDweller } from '../../helpers/dwellerFixtures'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock())

const dweller1 = {
  id: 'd1',
  first_name: 'Alice',
  last_name: 'Smith',
  level: 5,
  thumbnail_url: null,
  gender: 'female',
  charisma: 10,
}

const dweller2 = {
  id: 'd2',
  first_name: 'Bob',
  last_name: 'Jones',
  level: 7,
  thumbnail_url: null,
  gender: 'male',
  charisma: 10,
}

type CardProps = InstanceType<typeof RelationshipCard>['$props']

const relationship = (overrides: Record<string, unknown> = {}) => ({
  id: '1',
  dweller_1_id: 'd1',
  dweller_2_id: 'd2',
  relationship_type: 'friend',
  affinity: 50,
  ...overrides,
})

const mountCard = (
  options: {
    relationship?: Record<string, unknown>
    children?: unknown[]
    pregnancy?: unknown
    generation?: number
    dweller1?: Record<string, unknown>
    dweller2?: Record<string, unknown>
  } = {}
) =>
  mount(RelationshipCard, {
    props: {
      relationship: relationship(options.relationship),
      dweller1: { ...dweller1, ...options.dweller1 },
      dweller2: { ...dweller2, ...options.dweller2 },
      children: options.children ?? [],
      pregnancy: options.pregnancy ?? null,
      generation: options.generation ?? 1,
    },
    global: {
      stubs: {
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

const actionableButton = (wrapper: ReturnType<typeof mount>, label: string) =>
  wrapper.findAll('button').find((button) => button.text().trim() === label)

describe('RelationshipCard', () => {
  it('renders one paired record with both identities', () => {
    const wrapper = mountCard()

    expect(wrapper.find('.relationship-record--grid').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('DWELLER 01')
    expect(wrapper.text()).not.toContain('DWELLER 02')

    const portraits = wrapper.findAll('.dweller-portrait-stub')
    expect(portraits).toHaveLength(2)
    expect(portraits[0].attributes('data-alt')).toBe('Alice Smith')
    expect(portraits[1].attributes('data-alt')).toBe('Bob Jones')

    const genderBadges = wrapper.findAll('.dweller-gender-stub')
    expect(genderBadges).toHaveLength(2)
    expect(genderBadges[0].attributes('data-gender')).toBe('female')
    expect(genderBadges[1].attributes('data-gender')).toBe('male')

    expect(wrapper.text()).toContain('C 10')
    expect(wrapper.text()).toContain('Human')
  })

  it.each([
    [
      'a growing bond at the backend pace',
      { affinity: 50, bond_change_per_tick: 3, same_race: true, average_charisma: 8 },
      [
        'Growing closer',
        '+3 hearts every minute',
        'Same race',
        'Charisma 8',
        '20 hearts until romance',
      ],
      [],
    ],
    [
      'a drifting bond with its race and Charisma factors',
      { affinity: 55, bond_change_per_tick: -2, same_race: false, average_charisma: 3 },
      ['Drifting apart', '−2 hearts every minute', 'Mixed races', 'Charisma 3'],
      ['Growing closer'],
    ],
    [
      'a resting bond while the pair is apart',
      { relationship_type: 'partner', affinity: 80, bond_change_per_tick: 0 },
      ['Bond resting', 'Living Quarters', '5 hearts until marriage'],
      ['Growing closer'],
    ],
    [
      'a full bond without a growth rate',
      { relationship_type: 'MARRIED', affinity: 100, bond_change_per_tick: 0 },
      ['Bond at full strength'],
      ['Living Quarters'],
    ],
  ] as const)('describes %s', (_name, overrides, present, absent) => {
    const wrapper = mountCard({ relationship: { bond_tick_seconds: 60, ...overrides } })

    for (const text of present) expect(wrapper.text()).toContain(text)
    for (const text of absent) expect(wrapper.text()).not.toContain(text)
  })

  it('renders a rivalry with hostility and discomfort reasons', () => {
    const wrapper = mountCard({
      relationship: {
        relationship_type: 'rival',
        affinity: -42,
        bond_change_per_tick: -1,
        bond_tick_seconds: 60,
        discomfort_severity: 'strong',
        discomfort_source: 'feral',
      },
    })

    expect(wrapper.text()).toContain('Rival')
    expect(wrapper.text()).toContain('HOSTILITY')
    expect(wrapper.text()).toContain('-42/100')
    expect(wrapper.text()).toContain('Feral ghoul unease')
    expect(wrapper.text()).toContain('Drifting apart')
    expect(wrapper.text()).not.toContain('Romance')
  })

  it.each([
    ['possible', {}, 'Human', 'Could start a family'],
    [
      'race',
      { dweller1: { visual_attributes: { race: 'ghoul' } } },
      'Ghoul',
      'Only Human pairs can have children',
    ],
  ] as const)(
    'explains family potential %s with the pair race',
    (potential, options, race, message) => {
      const wrapper = mountCard({
        relationship: { conception_potential: potential },
        ...(options as { dweller1?: Record<string, unknown> }),
      })

      expect(wrapper.text()).toContain(race)
      expect(wrapper.text()).toContain(message)
    }
  )

  it('gives an image and a fallback icon the same portrait frame', () => {
    const wrapper = mount(RelationshipCard, {
      props: {
        relationship: relationship(),
        dweller1: { ...dweller1, thumbnail_url: '/static/alice.png' },
        dweller2,
      },
      global: { stubs: { DwellerGenderBadge: true } },
    })

    const frames = wrapper.findAll('.dweller-portrait-frame')
    expect(frames).toHaveLength(2)
    expect(frames[0].find('img').exists()).toBe(true)
    expect(frames[1].find('[role="img"]').exists()).toBe(true)
  })

  describe('badge variant per relationship type', () => {
    it.each([
      { type: 'acquaintance', expectVariant: 'outline', label: 'Acquaintance' },
      { type: 'friend', expectVariant: 'default', label: 'Friend' },
      { type: 'romantic', expectVariant: 'outline', label: 'Romantic' },
      { type: 'partner', expectVariant: 'outline', label: 'Partner' },
      { type: 'MARRIED', expectVariant: 'default', label: 'Married' },
      { type: 'ex', expectVariant: 'secondary', label: 'Ex' },
    ])('$type badge shows the correct variant', ({ type, expectVariant, label }) => {
      const wrapper = mountCard({ relationship: { relationship_type: type } })

      const badge = wrapper.find('.relationship-badge')
      expect(badge.text()).toBe(label)
      expect(badge.attributes('data-variant')).toBe(expectVariant)
    })

    it('defaults to the friend variant for an unknown type', () => {
      const wrapper = mountCard({ relationship: { relationship_type: 'unknown_type' } })

      expect(wrapper.find('.relationship-badge').attributes('data-variant')).toBe('default')
    })

    it('marks a marriage with a heart icon', () => {
      const wrapper = mountCard({ relationship: { relationship_type: 'MARRIED', affinity: 90 } })

      const badge = wrapper.find('.relationship-badge')
      expect(badge.text()).toContain('Married')
      expect(badge.find('.icon-mock').attributes('data-icon')).toBe('mdi:heart')
    })
  })

  describe('action buttons per stage', () => {
    it.each([
      [85, true],
      [84, false],
    ])('offers Marry to partners at %i affinity: %s', (affinity, offered) => {
      const wrapper = mountCard({ relationship: { relationship_type: 'partner', affinity } })

      if (offered) expect(wrapper.text()).toContain('Marry')
      else expect(wrapper.text()).not.toContain('Marry')
    })

    it.each([
      [false, 'Already committed'],
      [true, undefined],
    ] as const)(
      'sets the Partner action availability for can_make_partners=%s',
      (can_make_partners, title) => {
        const wrapper = mountCard({
          relationship: { relationship_type: 'romantic', affinity: 75, can_make_partners },
        })

        const partnerButton = actionableButton(wrapper, 'Partner')
        expect(partnerButton).toBeDefined()
        expect(partnerButton!.attributes('disabled') !== undefined).toBe(!can_make_partners)
        if (title) expect(partnerButton!.attributes('title')).toContain(title)
      }
    )

    it('shows a Break Up button for married relationships', () => {
      const wrapper = mountCard({ relationship: { relationship_type: 'MARRIED', affinity: 90 } })

      expect(wrapper.text()).toContain('Break Up')
    })
  })

  it('treats both dweller identities as direct roster links', async () => {
    const wrapper = mountCard()

    await wrapper.get('button[title="View Alice Smith"]').trigger('click')
    await wrapper.get('button[title="View Bob Jones"]').trigger('click')

    expect(wrapper.emitted('select-dweller')).toEqual([['d1'], ['d2']])
  })

  describe('family strip for partner relationships', () => {
    const child = makeDweller({
      id: 'c1',
      first_name: 'Kid',
      last_name: 'Smith',
      age_group: 'child',
      gender: 'male',
      rarity: 'common',
      happiness: 90,
    })
    const pregnancy = (is_due: boolean) => ({
      id: 'p1',
      mother_id: 'd1',
      father_id: 'd2',
      status: 'pregnant',
      is_due,
    })

    it.each([
      [
        'a child',
        { relationship: { relationship_type: 'partner' }, children: [child] },
        ['Children (1)', 'Kid'],
      ],
      [
        'a not-yet-pregnant couple',
        { relationship: { relationship_type: 'partner' } },
        ['No children yet'],
      ],
      [
        'a pregnant couple',
        {
          relationship: { relationship_type: 'partner' },
          children: [child],
          pregnancy: pregnancy(false),
        },
        ['GEN 1', 'Children (1)', 'Expecting'],
      ],
      [
        'a pregnancy that is due',
        { relationship: { relationship_type: 'partner' }, pregnancy: pregnancy(true) },
        ['Due!'],
      ],
      ['a couple with no pregnancy', { relationship: { relationship_type: 'partner' } }, ['GEN 1']],
    ] as const)('renders the family strip for %s', (_name, options, present) => {
      const wrapper = mountCard(options as Parameters<typeof mountCard>[0])

      for (const text of present) expect(wrapper.text()).toContain(text)
    })

    it('does not render the family strip for non-partner relationships', () => {
      const wrapper = mountCard({ children: [child] })

      expect(wrapper.text()).not.toContain('Children')
      expect(wrapper.text()).not.toContain('No children yet')
    })

    it('shows no expecting or due chip without a pregnancy', () => {
      const wrapper = mountCard({ relationship: { relationship_type: 'partner' } })

      expect(wrapper.text()).not.toContain('Expecting')
      expect(wrapper.text()).not.toContain('Due!')
    })

    it('swaps the expecting chip for a due chip when the pregnancy is due', () => {
      const wrapper = mountCard({
        relationship: { relationship_type: 'partner' },
        pregnancy: pregnancy(true),
      })

      expect(wrapper.text()).not.toContain('Expecting')
    })

    it('shows family potential for partners', () => {
      const wrapper = mountCard({
        relationship: { relationship_type: 'partner', conception_potential: 'possible' },
      })

      expect(wrapper.text()).toContain('Could start a family')
    })
  })
})
