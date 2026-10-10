import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SupplySliders from '@/modules/progression/components/party/SupplySliders.vue'
import { Slider } from '@/core/components/ui/slider'

const mountSliders = (props: Record<string, unknown> = {}) =>
  mount(SupplySliders, {
    props: {
      selectedStimpaks: 0,
      selectedRadaways: 0,
      maxStimpaks: 0,
      maxRadaways: 0,
      stimpakMax: 0,
      radawayMax: 0,
      ...props,
    },
  })

describe('SupplySliders', () => {
  it('renders the selected/max labels and the slider bounds', () => {
    const wrapper = mountSliders({
      selectedStimpaks: 3,
      selectedRadaways: 2,
      maxStimpaks: 5,
      maxRadaways: 4,
      stimpakMax: 5,
      radawayMax: 4,
    })

    const texts = wrapper.findAll('.w-14').map((el) => el.text())
    expect(texts).toEqual(['3 / 5', '2 / 4'])

    const sliders = wrapper.findAllComponents(Slider)
    expect(sliders.map((s) => s.props('max'))).toEqual([5, 4])
    expect(sliders.map((s) => s.props('disabled'))).toEqual([false, false])
  })

  it('disables each slider at zero availability', () => {
    const wrapper = mountSliders({ maxStimpaks: 0, maxRadaways: 0, stimpakMax: 0, radawayMax: 0 })

    const sliders = wrapper.findAllComponents(Slider)
    expect(sliders.map((s) => s.props('disabled'))).toEqual([true, true])
  })

  it('emits update:stimpaks and update:radaways from the sliders', async () => {
    const wrapper = mountSliders({ maxStimpaks: 5, maxRadaways: 5, stimpakMax: 5, radawayMax: 5 })
    const sliders = wrapper.findAllComponents(Slider)

    sliders[0].vm.$emit('update:modelValue', [4])
    sliders[1].vm.$emit('update:modelValue', [2])

    expect(wrapper.emitted('update:stimpaks')).toEqual([[[4]]])
    expect(wrapper.emitted('update:radaways')).toEqual([[[2]]])
  })
})
