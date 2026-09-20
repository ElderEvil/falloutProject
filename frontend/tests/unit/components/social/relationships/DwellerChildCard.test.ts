import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerChildCard from '@/modules/social/components/relationships/DwellerChildCard.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const child = {
  id: 'c1',
  first_name: 'Kid',
  last_name: 'Smith',
  age_group: 'child',
  gender: 'male',
  rarity: 'common',
  health: 80,
  max_health: 100,
  happiness: 90,
  strength: 5,
  perception: 5,
  endurance: 5,
  charisma: 5,
  intelligence: 5,
  agility: 5,
  luck: 5,
  thumbnail_url: null,
}

function mountCard(props = {}) {
  return mount(DwellerChildCard, {
    props: { dweller: child, ...props },
    global: { stubs: { Icon: true } },
  })
}

describe('DwellerChildCard', () => {
  it('renders the portrait, full name and health/happiness line', () => {
    const wrapper = mountCard()

    expect(wrapper.text()).toContain('Kid Smith')
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toBe('Kid Smith')
    expect(wrapper.text()).toContain('HP 80/100')
    expect(wrapper.text()).toContain('Happy 90%')
  })

  it('renders the seven SPECIAL stat letters', () => {
    const wrapper = mountCard()

    const letters = wrapper.findAll('.stat-letter')
    expect(letters).toHaveLength(7)
    expect(letters.map((l) => l.text()).join('')).toBe('SPECIAL')
  })

  it('emits select with the dweller id when clicked', async () => {
    const wrapper = mountCard()

    await wrapper.trigger('click')

    expect(wrapper.emitted('select')?.[0]).toEqual(['c1'])
  })
})