import { describe, expect, it, vi } from 'vitest'
import { createIconifyMock } from '../../helpers/mocks'
import { flushPromises, mount } from '@vue/test-utils'
import { Dialog } from '@/core/components/ui/dialog'
import TerminalModal from '@/core/components/common/TerminalModal.vue'

vi.mock('@iconify/vue', () => createIconifyMock())

const mountModal = (
  props: Record<string, unknown> = {},
  slots: Record<string, string> = {},
  attach = false
) =>
  mount(TerminalModal, {
    props: { open: true, ...props },
    slots,
    attachTo: attach ? document.body : undefined,
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })

describe('TerminalModal', () => {
  it('renders the title, icon, default content and header-extra slot', () => {
    const wrapper = mountModal(
      { title: 'Test Modal', icon: 'mdi:test' },
      {
        default: '<p class="body-copy">Body</p>',
        'header-extra': '<span class="extra-slot">Extra</span>',
      }
    )

    expect(wrapper.text()).toContain('Test Modal')
    expect(wrapper.find('.body-copy').exists()).toBe(true)
    expect(wrapper.find('.extra-slot').exists()).toBe(true)
    expect(wrapper.find('.icon-mock').attributes('data-icon')).toBe('mdi:test')
  })

  it('renders a custom title slot instead of the title prop', () => {
    const wrapper = mountModal({ title: 'Ignored' }, { title: '<span class="custom-title">Custom</span>' })

    expect(wrapper.find('.custom-title').text()).toBe('Custom')
    expect(wrapper.text()).not.toContain('Ignored')
  })

  it('omits the footer when no footer slot is provided', () => {
    const wrapper = mountModal()

    expect(wrapper.find('[data-slot="dialog-footer"]').exists()).toBe(false)
  })

  it('renders footer slot content inside the dialog footer', () => {
    const wrapper = mountModal({}, { footer: '<button class="footer-action">Go</button>' })

    const footer = wrapper.find('[data-slot="dialog-footer"]')
    expect(footer.exists()).toBe(true)
    expect(footer.find('.footer-action').exists()).toBe(true)
  })

  it('hides the footer when showFooter is false', () => {
    const wrapper = mountModal(
      { showFooter: false },
      { footer: '<button class="footer-action">Go</button>' }
    )

    expect(wrapper.find('[data-slot="dialog-footer"]').exists()).toBe(false)
  })

  it('maps size and maxHeight props onto the dialog content classes', () => {
    const wrapper = mountModal({ size: 'xl', maxHeight: '65' })
    const classes = wrapper.get('[data-slot="dialog-content"]').attributes('class') ?? ''

    expect(classes).toContain('max-w-xl')
    expect(classes).toContain('sm:max-w-xl')
    expect(classes).toContain('max-h-[65vh]')
  })

  it('defaults to the md/75 canonical variant', () => {
    const wrapper = mountModal()
    const classes = wrapper.get('[data-slot="dialog-content"]').attributes('class') ?? ''

    expect(classes).toContain('max-w-md')
    expect(classes).toContain('max-h-[75vh]')
    expect(classes).toContain('crt-screen')
    expect(classes).toContain('border-theme-primary')
  })

  it('emits update:open and close when the dialog closes', () => {
    const wrapper = mountModal()

    wrapper.findComponent(Dialog).vm.$emit('update:open', false)

    expect(wrapper.emitted('update:open')).toEqual([[false]])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits update:open but not close when the dialog opens', () => {
    const wrapper = mountModal({ open: false })

    wrapper.findComponent(Dialog).vm.$emit('update:open', true)

    expect(wrapper.emitted('update:open')).toEqual([[true]])
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('closes on Escape', async () => {
    const wrapper = mountModal()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()

    expect(wrapper.emitted('update:open')).toEqual([[false]])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('closes on the header close button', async () => {
    const wrapper = mountModal()

    await wrapper.get('[data-slot="dialog-close"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('update:open')).toEqual([[false]])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('closes on backdrop pointer down', async () => {
    const wrapper = mountModal({}, {}, true)

    await new Promise((resolve) => setTimeout(resolve, 0))
    wrapper
      .get('[data-slot="dialog-overlay"]')
      .element.dispatchEvent(
        new PointerEvent('pointerdown', {
          bubbles: true,
          button: 0,
          pointerType: 'mouse',
          isPrimary: true,
        })
      )
    await flushPromises()

    expect(wrapper.emitted('update:open')).toEqual([[false]])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
