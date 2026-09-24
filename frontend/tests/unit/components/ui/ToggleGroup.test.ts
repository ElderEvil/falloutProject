import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { ToggleGroup, ToggleGroupItem } from '@/core/components/ui/toggle-group'

function mountGroup(modelValue = 'normal') {
  return mount({
    components: { ToggleGroup, ToggleGroupItem },
    template: `
      <ToggleGroup type="single" :model-value="value" @update:model-value="value = $event">
        <ToggleGroupItem value="off" aria-label="Set glow to Off">Off</ToggleGroupItem>
        <ToggleGroupItem value="normal" aria-label="Set glow to Normal">Normal</ToggleGroupItem>
        <ToggleGroupItem value="strong" aria-label="Set glow to Strong">Strong</ToggleGroupItem>
      </ToggleGroup>
    `,
    data: () => ({ value: modelValue }),
  })
}

function items(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('[data-slot="toggle-group-item"]')
}

describe('ToggleGroup', () => {
  it('renders single-select options with pressed state', () => {
    const wrapper = mountGroup('normal')
    const all = items(wrapper)

    expect(all).toHaveLength(3)
    expect(wrapper.find('[aria-label="Set glow to Normal"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.find('[aria-label="Set glow to Off"]').attributes('aria-pressed')).toBe('false')
  })

  it('emits the item value on click', async () => {
    const wrapper = mountGroup('normal')

    await wrapper.find('[aria-label="Set glow to Strong"]').trigger('click')

    expect(wrapper.vm.value).toBe('strong')
  })

  it('does not emit when a disabled item is clicked', async () => {
    const wrapper = mount({
      components: { ToggleGroup, ToggleGroupItem },
      template: `
        <ToggleGroup type="single" :model-value="value" @update:model-value="value = $event">
          <ToggleGroupItem value="off" :disabled="true" aria-label="Set glow to Off">Off</ToggleGroupItem>
        </ToggleGroup>
      `,
      data: () => ({ value: 'normal' as string | undefined }),
    })

    await wrapper.find('[aria-label="Set glow to Off"]').trigger('click')

    expect(wrapper.vm.value).toBe('normal')
  })
})
