import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ChildChip from '@/modules/social/components/relationships/ChildChip.vue'

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

function mountChip() {
  return mount(ChildChip, {
    props: { dweller: child },
    global: { stubs: { Icon: true } },
  })
}

describe('ChildChip', () => {
  it('renders the portrait alt and the first name only', () => {
    const wrapper = mountChip()

    expect(wrapper.find('[aria-label="Kid Smith"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Kid')
    expect(wrapper.text()).not.toContain('Smith')
  })

  it('emits select with the dweller id when clicked', async () => {
    const wrapper = mountChip()

    await wrapper.trigger('click')

    const emitted = wrapper.emitted('select')
    expect(emitted).toBeTruthy()
    expect((emitted as unknown[])[0][0]).toBe('c1')
  })
})
