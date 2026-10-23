import { describe, it, expect, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import RadioControls from '@/modules/rooms/components/RadioControls.vue'

vi.mock('@iconify/vue', () => createIconifyMock())

function mountControls(mode: string) {
  return mount(RadioControls, {
    props: {
      localRadioMode: mode,
      isRecruiting: false,
      manualRecruitCost: 100,
      assignedDwellers: [],
    },
    global: {
      stubs: { Icon: true },
    },
  })
}

describe('RadioControls status dot', () => {
  it('marks the dot as recruiting (danger) in recruitment mode', () => {
    const wrapper = mountControls('recruitment')

    expect(wrapper.text()).toContain('Recruiting')
    // jsdom has no CSS pipeline, so the danger/success color requirement is
    // asserted on the class attr: the state hook is the requirement itself.
    expect(wrapper.get('.status-dot').attributes('class')).toMatch(/(^|\s)recruiting(\s|$)/)
  })

  it('leaves the dot in broadcasting (success) state otherwise', () => {
    const wrapper = mountControls('happiness')

    expect(wrapper.text()).toContain('Broadcasting')
    expect(wrapper.get('.status-dot').attributes('class')).not.toMatch(/(^|\s)recruiting(\s|$)/)
  })
})
