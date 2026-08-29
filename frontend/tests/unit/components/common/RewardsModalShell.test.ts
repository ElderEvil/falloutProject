import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RewardsModalShell from '@/core/components/common/RewardsModalShell.vue'

// Teleport escapes the test wrapper; stub it to render inline.
const mountShell = (props: Record<string, unknown>, slots?: Record<string, string>) =>
  mount(RewardsModalShell, {
    props: { show: true, title: 'Test', ...props },
    slots,
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })

describe('RewardsModalShell', () => {
  it('renders title and body content when shown', () => {
    const wrapper = mountShell({ title: 'Exploration Complete!' }, { default: '<p>Reward body content</p>' })

    expect(wrapper.get('.title').text()).toBe('Exploration Complete!')
    expect(wrapper.get('.modal-body').text()).toBe('Reward body content')
  })

  it('renders nothing when show is false', () => {
    const wrapper = mount(RewardsModalShell, {
      props: { show: false, title: 'Hidden' },
      slots: { default: '<p>content</p>' },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.find('.modal-overlay').exists()).toBe(false)
  })

  it('emits close when the overlay is clicked', async () => {
    const wrapper = mountShell({}, { default: '<p>body</p>' })

    await wrapper.get('.modal-overlay').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('does not emit close when the content area is clicked', async () => {
    const wrapper = mountShell({}, { default: '<p>body</p>' })

    await wrapper.get('.modal-content').trigger('click')

    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('emits close from the header close button', async () => {
    const wrapper = mountShell({}, { default: '<p>body</p>' })

    await wrapper.get('.close-btn').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('renders footer slot content when provided', () => {
    const wrapper = mountShell({}, { default: '<p>body</p>', footer: '<button>Claim</button>' })

    expect(wrapper.get('.modal-footer').text()).toBe('Claim')
  })

  it('hides the footer when no footer slot is provided', () => {
    const wrapper = mountShell({}, { default: '<p>body</p>' })

    expect(wrapper.find('.modal-footer').exists()).toBe(false)
  })

  it('applies the custom maxWidth prop', () => {
    const wrapper = mountShell({ maxWidth: '600px' }, { default: '<p>body</p>' })

    expect(wrapper.get('.modal-content').attributes('style')).toContain('max-width: 600px')
  })
})
