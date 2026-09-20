import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import CoupleFamilyDiagram from '@/modules/social/components/relationships/CoupleFamilyDiagram.vue'
import DwellerChildCard from '@/modules/social/components/relationships/DwellerChildCard.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const parent1 = { id: 'd1', first_name: 'John', last_name: 'Smith' }
const parent2 = { id: 'd2', first_name: 'Jane', last_name: 'Smith' }
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

function mountDiagram(props = {}) {
  return mount(CoupleFamilyDiagram, {
    props: { dweller1: parent1, dweller2: parent2, ...props },
    global: { stubs: { Icon: true } },
  })
}

describe('CoupleFamilyDiagram', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function setDwellers(dwellers: unknown[]) {
    const store = useDwellerStore()
    const filter = store.filter
    filter.allDwellers = dwellers as never
  }

  it('does not repeat the partner names (they are shown by the relationship card)', () => {
    setDwellers([])
    const wrapper = mountDiagram()

    expect(wrapper.text()).not.toContain('John Smith')
    expect(wrapper.text()).not.toContain('Jane Smith')
  })

  it('shows a Children heading with the count and a child card', () => {
    setDwellers([{ ...child, parent_1_id: 'd1', parent_2_id: 'd2' }])
    const wrapper = mountDiagram()

    expect(wrapper.text()).toContain('Children (1)')
    expect(wrapper.findComponent(DwellerChildCard).exists()).toBe(true)
    expect(wrapper.text()).toContain('Kid Smith')
  })

  it('emits select with the child id when a child card is clicked', async () => {
    setDwellers([{ ...child, parent_1_id: 'd1', parent_2_id: 'd2' }])
    const wrapper = mountDiagram()

    const childCard = wrapper.findComponent(DwellerChildCard)
    expect(childCard.exists()).toBe(true)
    await childCard.trigger('click')

    const emitted = wrapper.emitted('select')
    expect(emitted).toBeTruthy()
    expect((emitted as unknown[])[0][0]).toBe('c1')
  })

  it('does not show a child of a different couple', () => {
    setDwellers([{ ...child, parent_1_id: 'd9', parent_2_id: 'd8' }])
    const wrapper = mountDiagram()

    expect(wrapper.text()).toContain('No children yet')
    expect(wrapper.text()).not.toContain('Kid')
  })

  it('shows a placeholder when the couple has no children', () => {
    setDwellers([])
    const wrapper = mountDiagram()

    expect(wrapper.text()).toContain('No children yet')
  })
})
