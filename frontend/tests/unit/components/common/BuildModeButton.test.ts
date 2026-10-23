import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { Icon } from '@iconify/vue'
import BuildModeButton from '@/core/components/common/BuildModeButton.vue'

describe('BuildModeButton', () => {
  it('offers an onboarding target only while the button starts construction', async () => {
    const wrapper = mount(BuildModeButton, {
      props: { buildModeActive: false },
    })

    expect(wrapper.find('[data-onboarding="build"]').exists()).toBe(true)

    await wrapper.setProps({ buildModeActive: true })

    expect(wrapper.find('button').text()).toContain('Cancel Building')
    expect(wrapper.find('[data-onboarding="build"]').exists()).toBe(false)

    await wrapper.setProps({ buildModeActive: false })

    expect(wrapper.find('[data-onboarding="build"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('should render the build icon', () => {
    const wrapper = mount(BuildModeButton, {
      props: { buildModeActive: false },
    })

    const icon = wrapper.findComponent(Icon)
    expect(icon.exists()).toBe(true)
    expect(icon.props('icon')).toBe('mdi:hammer')
  })

  it('should render button text and badge', () => {
    const wrapper = mount(BuildModeButton, {
      props: { buildModeActive: false },
    })

    expect(wrapper.text()).toContain('Build')
    expect(wrapper.text()).not.toContain('Build Mode')
    expect(wrapper.text()).toContain('B')
  })

  it('should show cancel mode when active', () => {
    const wrapper = mount(BuildModeButton, {
      props: { buildModeActive: true },
    })

    expect(wrapper.text()).toContain('Cancel Building')
    expect(wrapper.text()).toContain('ESC')
  })

  it('should emit toggleBuildMode on click', async () => {
    const wrapper = mount(BuildModeButton, {
      props: { buildModeActive: false },
    })

    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('toggleBuildMode')).toBeTruthy()
  })
})
