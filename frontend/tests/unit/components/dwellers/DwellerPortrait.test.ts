import { describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<span class="icon-mock" :data-icon="icon" />' })
)

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

  it('allows scene callers to anchor portraits on the head', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        imageUrl: 'example.com/lucy.png',
        alt: 'Lucy MacLean portrait',
        objectPosition: 'center top',
      },
    })

    expect(wrapper.find('img').attributes('style')).toContain('object-position: center top')
  })

  it('applies a body-size scale to the image', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        imageUrl: 'example.com/lucy.png',
        alt: 'Lucy MacLean portrait',
        scale: 1.18,
      },
    })

    expect(wrapper.find('img').attributes('style')).toContain('--portrait-scale: 1.18')
  })

  it('uses the API origin for backend static portraits', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        thumbnailUrl: '/static/portraits/lucy.png',
        alt: 'Lucy MacLean portrait',
      },
    })

    expect(wrapper.find('img').attributes('src')).toBe(
      'http://localhost:8000/static/portraits/lucy.png'
    )
  })

  it('applies the curated card zoom by default', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        thumbnailUrl: '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp',
        alt: 'Portrait',
      },
    })

    expect(wrapper.find('img').attributes('class')).toContain('default-portrait-zoom')
  })

  it('can opt out of the curated zoom for scene portraits', () => {
    const wrapper = mount(DwellerPortrait, {
      props: {
        thumbnailUrl: '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp',
        alt: 'Portrait',
        zoom: false,
      },
    })

    expect(wrapper.find('img').attributes('class')).not.toContain('default-portrait-zoom')
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

  it('renders a provided fallback slot when the portrait cannot be loaded', async () => {
    const wrapper = mount(DwellerPortrait, {
      props: { imageUrl: 'example.com/lucy.png', alt: 'Lucy MacLean portrait' },
      slots: { fallback: '<span class="custom-fallback" />' },
    })

    await wrapper.find('img').trigger('error')

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.custom-fallback').exists()).toBe(true)
    expect(wrapper.find('.icon-mock').exists()).toBe(false)
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
