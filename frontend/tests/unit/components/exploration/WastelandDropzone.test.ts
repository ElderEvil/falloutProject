import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import WastelandDropzone from '@/modules/exploration/components/WastelandDropzone.vue'

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

describe('WastelandDropzone', () => {
  it('renders the wasteland title and subtitle', () => {
    const wrapper = mount(WastelandDropzone)

    expect(wrapper.text()).toContain('The Wasteland')
    expect(wrapper.text()).toContain('Drag dwellers here to send them exploring')
  })

  it('renders slot content', () => {
    const wrapper = mount(WastelandDropzone, {
      slots: {
        default: '<div class="slot-content">Child Content</div>',
      },
    })

    expect(wrapper.find('.slot-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Child Content')
  })

  it('shows drop indicator when drag-over class is active', async () => {
    const wrapper = mount(WastelandDropzone)

    // Simulate dragover
    const dropzone = wrapper.find('.wasteland-dropzone')
    await dropzone.trigger('dragover', {
      dataTransfer: { dropEffect: 'none' },
      preventDefault: vi.fn(),
    })

    expect(wrapper.find('.drag-over').exists()).toBe(true)
    expect(wrapper.find('.drop-indicator').exists()).toBe(true)
    expect(wrapper.text()).toContain('Release to send!')
  })

  it('removes drag-over state on dragleave', async () => {
    const wrapper = mount(WastelandDropzone)

    const dropzone = wrapper.find('.wasteland-dropzone')
    await dropzone.trigger('dragover', {
      dataTransfer: { dropEffect: 'none' },
      preventDefault: vi.fn(),
    })
    expect(wrapper.find('.drag-over').exists()).toBe(true)

    await dropzone.trigger('dragleave')
    expect(wrapper.find('.drag-over').exists()).toBe(false)
  })

  it('emits drop-dweller with parsed payload on valid drop', async () => {
    const wrapper = mount(WastelandDropzone)

    const dropData = JSON.stringify({
      dwellerId: 'dweller-123',
      firstName: 'Test',
      lastName: 'Dweller',
      currentRoomId: 'room-456',
    })

    const dropzone = wrapper.find('.wasteland-dropzone')
    await dropzone.trigger('drop', {
      preventDefault: vi.fn(),
      dataTransfer: {
        getData: () => dropData,
      },
    })

    expect(wrapper.emitted('drop-dweller')).toHaveLength(1)
    expect(wrapper.emitted('drop-dweller')![0]).toEqual([
      {
        dwellerId: 'dweller-123',
        firstName: 'Test',
        lastName: 'Dweller',
        currentRoomId: 'room-456',
      },
    ])
  })

  it('emits drop-error on invalid JSON drop', async () => {
    const wrapper = mount(WastelandDropzone)

    const dropzone = wrapper.find('.wasteland-dropzone')
    await dropzone.trigger('drop', {
      preventDefault: vi.fn(),
      dataTransfer: {
        getData: () => 'not-json',
      },
    })

    expect(wrapper.emitted('drop-error')).toHaveLength(1)
    expect(wrapper.emitted('drop-error')![0]).toEqual([
      'Failed to send dweller to wasteland',
    ])
  })

  it('removes drag-over state on drop', async () => {
    const wrapper = mount(WastelandDropzone)

    const dropzone = wrapper.find('.wasteland-dropzone')
    await dropzone.trigger('dragover', {
      dataTransfer: { dropEffect: 'none' },
      preventDefault: vi.fn(),
    })
    expect(wrapper.find('.drag-over').exists()).toBe(true)

    await dropzone.trigger('drop', {
      preventDefault: vi.fn(),
      dataTransfer: {
        getData: () => JSON.stringify({ dwellerId: 'x', firstName: 'F', lastName: 'L' }),
      },
    })

    expect(wrapper.find('.drag-over').exists()).toBe(false)
  })
})
