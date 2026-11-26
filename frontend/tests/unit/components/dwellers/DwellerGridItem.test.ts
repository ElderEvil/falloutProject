import { describe, it, expect, beforeEach } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerGridItem from '@/modules/dwellers/components/grid/DwellerGridItem.vue'
import HealthRadiationBar from '@/core/components/common/HealthRadiationBar.vue'

const mockDweller = {
  id: '123',
  first_name: 'John',
  last_name: 'Doe',
  level: 5,
  health: 80,
  max_health: 100,
  happiness: 75,
  strength: 8,
  perception: 6,
  endurance: 7,
  charisma: 5,
  intelligence: 4,
  agility: 6,
  luck: 7,
  status: 'working',
  room_id: 'room-123',
}

describe('DwellerGridItem', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  type ItemProps = InstanceType<typeof DwellerGridItem>['$props']

  const mountItem = (overrides: Partial<ItemProps> = {}) =>
    mount(DwellerGridItem, {
      props: { dweller: mockDweller as never, roomName: 'Power Generator', ...overrides },
    })

  describe('job stat', () => {
    it.each([
      ['STR', 8, false, 'success'],
      ['INT', 5, false, 'warning'],
      ['CHA', 2, false, 'danger'],
      ['Power', 18, true, 'warning'],
    ] as const)('renders %s %i in the %s tone', (label, value, isPower, tone) => {
      const wrapper = mountItem({ roomStat: { icon: 'mdi:test-tube', label, value, isPower } })

      expect(wrapper.get('.job-stat').text()).toContain(label)
      expect(wrapper.get('.job-stat').text()).toContain(value.toString())
      expect(wrapper.find('.job-stat-icon').exists()).toBe(true)
      expect(wrapper.get('.job-stat-value').classes()).toContain(`text-${tone}`)
    })

    it('renders no job stat when the room has no stat', () => {
      const wrapper = mountItem()

      expect(wrapper.find('.job-stat').exists()).toBe(false)
    })

    it.each([
      ['mdi:eye', 'PER', 6],
      ['mdi:heart', 'END', 7],
      ['mdi:account-voice', 'CHA', 5],
      ['mdi:brain', 'INT', 4],
      ['mdi:run', 'AGI', 6],
      ['mdi:four-leaf-clover', 'LCK', 7],
    ])('renders the provided %s label and value', (icon, label, value) => {
      const wrapper = mountItem({
        roomName: 'Test Room',
        roomStat: { icon, label, value, isPower: false },
      })

      expect(wrapper.get('.job-stat').text()).toContain(label)
      expect(wrapper.get('.job-stat').text()).toContain(value.toString())
    })
  })

  it('uses radiation as an absolute share of maximum health', () => {
    const wrapper = mountItem({ dweller: { ...mockDweller, max_health: 200, radiation: 25 } })

    expect(wrapper.findComponent(HealthRadiationBar).props('radiation')).toBe(12.5)
  })

  it('floats health and assigned SPECIAL progress over the portrait', () => {
    const wrapper = mountItem({
      roomStat: { icon: 'mdi:arm-flex', label: 'STR', value: 8, isPower: false },
    })

    const meters = wrapper.get('.portrait-meters')
    expect(meters.element.parentElement?.classList.contains('thumbnail-container')).toBe(true)
    expect(meters.get('[role="progressbar"][aria-label="John Doe health"]')).toBeDefined()
    expect(
      meters.get('[role="progressbar"][aria-label="STR progress"]').attributes('aria-valuenow')
    ).toBe('80')
  })

  it('anchors scaled portraits to the bottom of the grid frame', () => {
    const wrapper = mountItem({
      dweller: { ...mockDweller, age_group: 'teen', thumbnail_url: '/static/portrait.webp' },
    })

    expect(wrapper.get('img').attributes('style')).toContain('object-position: center bottom')
  })

  it.each([
    ['teen', 'human', 'thumbnail-image--small', '0.8'],
    ['adult', 'super_mutant', 'thumbnail-image--large', '1.18'],
  ])('scales %s %s portraits to reflect body size', (age_group, race, scaleClass, scale) => {
    const wrapper = mountItem({
      dweller: {
        ...mockDweller,
        age_group,
        visual_attributes: { race },
        thumbnail_url: '/static/portrait.webp',
      },
    })

    const image = wrapper.get('img')
    expect(image.classes()).toContain(scaleClass)
    expect(image.attributes('style')).toContain(`--portrait-scale: ${scale}`)
  })

  it('renders the dweller name and level', () => {
    const wrapper = mountItem()

    expect(wrapper.text()).toContain('John Doe')
    expect(wrapper.text()).toContain('5')
  })

  it('does not render the legacy AI portrait action', () => {
    const wrapper = mountItem({
      dweller: {
        ...mockDweller,
        thumbnail_url: '/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp',
        is_default_portrait: true,
      },
    })

    expect(wrapper.find('.ai-generate-button').exists()).toBe(false)
  })
})
