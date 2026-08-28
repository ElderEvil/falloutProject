import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<span class="icon-mock" :data-icon="icon" />',
  },
}))

describe('DwellerPortrait', () => {
  it('prefers and normalizes the full portrait URL', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        imageUrl: 'example.com/lucy.png',
        thumbnailUrl: 'example.com/lucy-thumb.png',
        alt: 'Lucy MacLean portrait',
      },
    })

    expect(wrapper.find('img').attributes()).toMatchObject({
      src: 'http://example.com/lucy.png',
      alt: 'Lucy MacLean portrait',
    })
  })

  it('uses the thumbnail when no full portrait is available', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        imageUrl: '',
        thumbnailUrl: 'example.com/lucy-thumb.png',
        alt: 'Lucy MacLean portrait',
      },
    })

    expect(wrapper.find('img').attributes('src')).toBe('http://example.com/lucy-thumb.png')
    expect(wrapper.find('img').attributes('style')).toContain('object-position: center top')
  })

  it('prefers the thumbnail for compact previews when both sources exist', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        imageUrl: 'example.com/lucy.png',
        thumbnailUrl: 'example.com/lucy-thumb.png',
        preferThumbnail: true,
        alt: 'Lucy MacLean portrait',
      },
    })

    expect(wrapper.find('img').attributes('src')).toBe('http://example.com/lucy-thumb.png')
  })

  it('uses the API origin for backend static portraits', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        thumbnailUrl: '/static/portraits/lucy.png',
        alt: 'Lucy MacLean portrait',
        urlMode: 'static',
      },
    })

    expect(wrapper.find('img').attributes('src')).toBe(
      'http://localhost:8000/static/portraits/lucy.png'
    )
  })

  it('renders an accessible account fallback when neither image exists', () => {
    const wrapper = mount(DwellerPortrait, {
      props: { alt: 'Unknown dweller portrait' },
    })

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.icon-mock').attributes('data-icon')).toBe('mdi:account')
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toBe('Unknown dweller portrait')
  })

  it('renders its fallback when the portrait cannot be loaded', async () => {
    const wrapper = mount(DwellerPortrait, {
      props: { imageUrl: 'example.com/lucy.png', alt: 'Lucy MacLean portrait' },
    })

    await wrapper.find('img').trigger('error')

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toBe('Lucy MacLean portrait')
  })

  it('tries again when the portrait URL changes', async () => {
    const wrapper = mount(DwellerPortrait, {
      props: { imageUrl: 'example.com/lucy.png', alt: 'Lucy MacLean portrait' },
    })

    await wrapper.find('img').trigger('error')
    await wrapper.setProps({ imageUrl: 'example.com/lucy-updated.png' })

    expect(wrapper.find('img').attributes('src')).toBe('http://example.com/lucy-updated.png')
  })
})
