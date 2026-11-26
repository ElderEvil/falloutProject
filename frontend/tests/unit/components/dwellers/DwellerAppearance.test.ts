import { beforeEach, describe, expect, it } from 'vite-plus/test'
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

  it.each([
    ['only identity fields', { race: 'human' }],
    ['no visual attributes at all', null],
    ['every non-identity field empty', { race: 'human', hair_style: null, eye_color: '' }],
  ])('shows the empty state when there are %s', async (_name, visualAttributes) => {
    const wrapper = mountAppearance(visualAttributes as Record<string, unknown> | null)

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(false)
    expect(wrapper.text()).toContain('No appearance yet')
  })

  it.each([
    [{ race: 'super_mutant', state_of_being: 'behemoth', height: 'tall' }, 'Behemoth'],
    [{ race: 'synth', state_of_being: 'gen_1', hair_style: 'ponytail' }, 'Gen I'],
  ] as const)('renders state of being %o as a text row', async (visualAttributes, state) => {
    const wrapper = mountAppearance(visualAttributes as unknown as Record<string, unknown>)

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Dweller identity"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('State:')
    expect(wrapper.text()).toContain(state)
    expect(wrapper.find('.badge-state-marker').exists()).toBe(false)
  })

  it('does not render legacy appearance actions', async () => {
    const wrapper = mountAppearance({ race: 'human' })

    await nextTick()

    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('renders generated attributes once they are substantial', async () => {
    const wrapper = mountAppearance({ race: 'human', hair_style: 'ponytail', eye_color: 'green' })

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('No appearance yet')
    expect(wrapper.text()).toContain('Hair')
  })
})
