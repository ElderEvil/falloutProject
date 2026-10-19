import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import DwellerAppearance from '@/modules/dwellers/components/DwellerAppearance.vue'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'

describe('DwellerAppearance', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mountAppearance = (
    visualAttributes: Record<string, unknown> | null,
    age_group = 'adult'
  ) => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref({
        first_name: 'Amata',
        age_group,
        visual_attributes: visualAttributes,
      }) as never,
    })
    return mountWithDwellerContext(DwellerAppearance, { context: ctx })
  }

  it.each(['child', 'teen'])('hides equipment-derived appearance for a %s', (age_group) => {
    const wrapper = mountAppearance(
      { hair_style: 'ponytail', headgear: 'helmet', accessory: 'watch', object_held: 'rifle' },
      age_group
    )
    expect(wrapper.text()).toContain('Ponytail')
    expect(wrapper.text()).not.toContain('Helmet')
    expect(wrapper.text()).not.toContain('Watch')
    expect(wrapper.text()).not.toContain('Rifle')
  })

  it('shows the empty state when only identity fields exist', async () => {
    const wrapper = mountAppearance({ race: 'human' })

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(false)
    expect(wrapper.text()).toContain('No appearance yet')
  })

  it('shows the empty state when there are no visual attributes at all', async () => {
    const wrapper = mountAppearance(null)

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(false)
    expect(wrapper.text()).toContain('No appearance yet')
  })

  it('shows the empty state when every non-identity field is empty', async () => {
    const wrapper = mountAppearance({ race: 'human', hair_style: null, eye_color: '' })

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(false)
    expect(wrapper.text()).toContain('No appearance yet')
  })

  it('omits synth generation from the appearance badge', async () => {
    const wrapper = mountAppearance({
      race: 'synth',
      state_of_being: 'gen_1',
      hair_style: 'ponytail',
    })

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Dweller identity"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Gen I')
  })

  it('renders generated attributes once they are substantial', async () => {
    const wrapper = mountAppearance({ race: 'human', hair_style: 'ponytail', eye_color: 'green' })

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('No appearance yet')
    expect(wrapper.text()).toContain('Hair')
  })
})
