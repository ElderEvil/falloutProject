import { describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<span class="icon-mock" :data-icon="icon" />' })
)

type PortraitProps = InstanceType<typeof DwellerPortrait>['$props']

const mountPortrait = (props: Partial<PortraitProps>, options: Record<string, unknown> = {}) =>
  mount(DwellerPortrait, { props: { alt: 'Lucy MacLean portrait', ...props }, ...options })

describe('DwellerPortrait', () => {
  it.each([
    [
      'the full portrait when both sources exist',
      { imageUrl: 'example.com/lucy.png', thumbnailUrl: 'example.com/lucy-thumb.png' },
      'http://example.com/lucy.png',
    ],
    [
      'the thumbnail when no full portrait is available',
      { imageUrl: '', thumbnailUrl: 'example.com/lucy-thumb.png' },
      'http://example.com/lucy-thumb.png',
    ],
    [
      'the thumbnail for compact previews',
      {
        imageUrl: 'example.com/lucy.png',
        thumbnailUrl: 'example.com/lucy-thumb.png',
        preferThumbnail: true,
      },
      'http://example.com/lucy-thumb.png',
    ],
    [
      'the API origin for backend static portraits',
      { thumbnailUrl: '/static/portraits/lucy.png' },
      'http://localhost:8000/static/portraits/lucy.png',
    ],
  ] as const)('prefers %s', (_name, props, src) => {
    const wrapper = mountPortrait(props)

    expect(wrapper.find('img').attributes('src')).toBe(src)
    expect(wrapper.find('img').attributes('alt')).toBe('Lucy MacLean portrait')
  })

  it('uses the head anchor the caller asks for', () => {
    const wrapper = mountPortrait({
      imageUrl: 'example.com/lucy.png',
      objectPosition: 'center top',
    })

    expect(wrapper.find('img').attributes('style')).toContain('object-position: center top')
  })

  it('applies a body-size scale to the image', () => {
    const wrapper = mountPortrait({ imageUrl: 'example.com/lucy.png', scale: 1.18 })

    expect(wrapper.find('img').attributes('style')).toContain('--portrait-scale: 1.18')
  })

  it.each([
    ['dweller_images', '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp'],
    ['legendary_dweller_images', '/static/legendary_dweller_images/FOS_Dw_Butch.png'],
  ])('applies the curated zoom by default to %s', (_folder, thumbnailUrl) => {
    const wrapper = mountPortrait({ thumbnailUrl })

    expect(wrapper.find('img').attributes('class')).toContain('default-portrait-zoom')
  })

  it('does not reserve a 1:2 canvas for legendary portraits', () => {
    const wrapper = mountPortrait({
      thumbnailUrl: '/static/legendary_dweller_images/FOS_Dw_Butch.png',
      alt: 'Butch portrait',
    })

    expect(wrapper.get('img').attributes('width')).toBeUndefined()
  })

  it('keeps non-humanoid companion art out of the human card framing', () => {
    const wrapper = mountPortrait({
      thumbnailUrl: '/static/legendary_dweller_images/FOS_Dw_Snip_Snip.png',
      alt: 'Snip Snip portrait',
    })

    const image = wrapper.get('img')
    expect(image.attributes('class')).not.toContain('default-portrait-zoom')
    expect(image.attributes('style')).toContain('object-fit: contain')
    expect(image.attributes('style')).toContain('object-position: center bottom')
  })

  it('reserves the curated thumbnail aspect ratio without sizing arbitrary uploads', () => {
    const curated = mountPortrait({
      thumbnailUrl: '/static/dweller_thumbnails/base/lucy.webp',
      alt: 'Lucy',
    })
    const upload = mountPortrait({ imageUrl: 'https://example.com/upload.png', alt: 'Upload' })

    expect(curated.get('img').attributes()).toMatchObject({ width: '150', height: '300' })
    expect(upload.get('img').attributes('width')).toBeUndefined()
  })

  it('can opt out of the curated zoom for scene portraits', () => {
    const wrapper = mountPortrait({
      thumbnailUrl: '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp',
      zoom: false,
    })

    expect(wrapper.find('img').attributes('class')).not.toContain('default-portrait-zoom')
  })

  it('renders an accessible account fallback when neither image exists', () => {
    const wrapper = mountPortrait({ alt: 'Unknown dweller portrait' })

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.icon-mock').attributes('data-icon')).toBe('mdi:account')
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toBe('Unknown dweller portrait')
  })

  it('renders its fallback when the portrait cannot be loaded', async () => {
    const wrapper = mountPortrait({ imageUrl: 'example.com/lucy.png' })

    await wrapper.find('img').trigger('error')

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toBe('Lucy MacLean portrait')
  })

  it('renders a provided fallback slot when the portrait cannot be loaded', async () => {
    const wrapper = mountPortrait(
      { imageUrl: 'example.com/lucy.png' },
      { slots: { fallback: '<span class="custom-fallback" />' } }
    )

    await wrapper.find('img').trigger('error')

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.custom-fallback').exists()).toBe(true)
    expect(wrapper.find('.icon-mock').exists()).toBe(false)
  })

  it('tries again when the portrait URL changes', async () => {
    const wrapper = mountPortrait({ imageUrl: 'example.com/lucy.png' })

    await wrapper.find('img').trigger('error')
    await wrapper.setProps({ imageUrl: 'example.com/lucy-updated.png' })

    expect(wrapper.find('img').attributes('src')).toBe('http://example.com/lucy-updated.png')
  })
})
