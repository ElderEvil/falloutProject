import { describe, it, expect, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import WastelandDropzone from '@/modules/exploration/components/WastelandDropzone.vue'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock())

function mountDropzone() {
  return mount(WastelandDropzone)
}

async function dragOver(wrapper: ReturnType<typeof mountDropzone>) {
  await wrapper.find('.wasteland-dropzone').trigger('dragover', {
    dataTransfer: { dropEffect: 'none' },
    preventDefault: vi.fn(),
  })
}

const dropPayload = (data: string) => ({
  preventDefault: vi.fn(),
  dataTransfer: { getData: () => data },
})

describe('WastelandDropzone', () => {
  it('renders the wasteland title, subtitle and onboarding anchor', () => {
    const wrapper = mountDropzone()

    expect(wrapper.text()).toContain('The Wasteland')
    expect(wrapper.text()).toContain('Drag dwellers here to send them exploring')
    expect(wrapper.find('[data-onboarding="wasteland"]').exists()).toBe(true)
  })

  it('renders slot content', () => {
    const wrapper = mount(WastelandDropzone, {
      slots: { default: '<div class="slot-content">Child Content</div>' },
    })

    expect(wrapper.find('.slot-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Child Content')
  })

  it('shows drop indicator when drag-over class is active', async () => {
    const wrapper = mountDropzone()

    await dragOver(wrapper)

    expect(wrapper.find('.drag-over').exists()).toBe(true)
    expect(wrapper.find('.drop-indicator').exists()).toBe(true)
    expect(wrapper.text()).toContain('Release to send!')
  })

  it('keeps the drop hint in the layout while dragging over so the zone cannot resize', async () => {
    const wrapper = mountDropzone()

    await dragOver(wrapper)

    // Hiding this line with `v-if` shortened the zone by a line, moving the
    // bottom border out from under a cursor parked on the edge and strobing
    // dragleave/dragover forever. `visibility` hides it without the shrink.
    expect(wrapper.find('.drag-hint').exists()).toBe(true)
    expect(wrapper.text()).toContain('Drag dwellers here to send them exploring')
  })

  it('ignores dragleave fired when the pointer crosses onto a child element', async () => {
    const wrapper = mount(WastelandDropzone, {
      slots: { default: '<div class="slot-content"></div>' },
    })
    const zone = wrapper.find('.wasteland-dropzone')
    await dragOver(wrapper)

    await zone.trigger('dragleave', { relatedTarget: wrapper.find('.slot-content').element })
    expect(wrapper.find('.drag-over').exists()).toBe(true)

    await zone.trigger('dragleave', { relatedTarget: document.body })
    expect(wrapper.find('.drag-over').exists()).toBe(false)
  })

  it.each([
    ['dragleave', undefined],
    ['drop', JSON.stringify({ dwellerId: 'x', firstName: 'F', lastName: 'L' })],
  ])('removes drag-over state on %s', async (event, data) => {
    const wrapper = mountDropzone()
    const dropzone = wrapper.find('.wasteland-dropzone')
    await dragOver(wrapper)
    expect(wrapper.find('.drag-over').exists()).toBe(true)

    await dropzone.trigger(event, data === undefined ? {} : dropPayload(data))

    expect(wrapper.find('.drag-over').exists()).toBe(false)
  })

  it('emits drop-dweller with parsed payload on valid drop', async () => {
    const wrapper = mountDropzone()
    const payload = {
      dwellerId: 'dweller-123',
      firstName: 'Test',
      lastName: 'Dweller',
      currentRoomId: 'room-456',
    }

    await wrapper.find('.wasteland-dropzone').trigger('drop', dropPayload(JSON.stringify(payload)))

    expect(wrapper.emitted('drop-dweller')).toEqual([[payload]])
  })

  it('emits drop-error on invalid JSON drop', async () => {
    const wrapper = mountDropzone()

    await wrapper.find('.wasteland-dropzone').trigger('drop', dropPayload('not-json'))

    expect(wrapper.emitted('drop-error')).toEqual([['Failed to send dweller to wasteland']])
  })
})
