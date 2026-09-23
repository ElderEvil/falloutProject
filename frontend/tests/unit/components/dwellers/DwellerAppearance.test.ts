import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import DwellerAppearance from '@/modules/dwellers/components/DwellerAppearance.vue'
import { createMockDwellerDetailContext, mountWithDwellerContext } from '../../helpers/dwellerDetailContext'

describe('DwellerAppearance', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mountAppearance = (visualAttributes: Record<string, unknown> | null) => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref({ first_name: 'Amata', visual_attributes: visualAttributes }) as never,
    })
    return mountWithDwellerContext(DwellerAppearance, { context: ctx })
  }

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

  it('renders generated attributes once they are substantial', async () => {
    const wrapper = mountAppearance({ race: 'human', hair_style: 'ponytail', eye_color: 'green' })

    await nextTick()

    expect(wrapper.find('.appearance-content').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('No appearance yet')
    expect(wrapper.text()).toContain('Hair')
  })
})
