import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ItemIcon from '@/core/components/common/ItemIcon.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<span class="icon-mock" :data-icon="icon" />',
  },
}))

describe('ItemIcon', () => {
  it('renders the registry icon for an edged weapon', () => {
    const wrapper = mount(ItemIcon, {
      props: { item: { weapon_subtype: 'edged' }, itemType: 'weapon' },
    })

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.icon-mock').attributes('data-icon')).toBe('mdi:sword')
  })

  it('renders the registry icon for a pistol', () => {
    const wrapper = mount(ItemIcon, {
      props: { item: { weapon_subtype: 'pistol' }, itemType: 'weapon' },
    })

    expect(wrapper.find('.icon-mock').attributes('data-icon')).toBe('mdi:pistol')
  })

  it('renders an img with the resolved URL when an image exists', () => {
    const wrapper = mount(ItemIcon, {
      props: { item: { image_url: 'https://example.com/knife.png', name: 'Combat Knife' }, itemType: 'weapon' },
    })

    const img = wrapper.get('img')
    expect(img.attributes('src')).toBe('https://example.com/knife.png')
    expect(img.attributes('alt')).toBe('Combat Knife')
  })

  it('resolves backend static paths against the API origin', () => {
    const wrapper = mount(ItemIcon, {
      props: { item: { image_url: '/static/items/knife.png' }, itemType: 'weapon' },
    })

    expect(wrapper.get('img').attributes('src')).toBe('http://localhost:8000/static/items/knife.png')
  })

  it('falls back to the icon when the image fails to load', async () => {
    const wrapper = mount(ItemIcon, {
      props: { item: { image_url: 'https://example.com/knife.png', weapon_subtype: 'edged' }, itemType: 'weapon' },
    })

    await wrapper.get('img').trigger('error')

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.icon-mock').attributes('data-icon')).toBe('mdi:sword')
  })

  it('defaults alt to the item name, then to Unknown Item', () => {
    const named = mount(ItemIcon, {
      props: { item: { image_url: 'https://example.com/knife.png', name: 'Ripper' }, itemType: 'weapon' },
    })
    expect(named.get('img').attributes('alt')).toBe('Ripper')

    const unnamed = mount(ItemIcon, {
      props: { item: { image_url: 'https://example.com/knife.png' }, itemType: 'weapon' },
    })
    expect(unnamed.get('img').attributes('alt')).toBe('Unknown Item')
  })

  it('passes through extra attrs to the rendered element', () => {
    const wrapper = mount(ItemIcon, {
      props: { item: { weapon_subtype: 'edged' }, itemType: 'weapon' },
      attrs: { 'data-testid': 'item-icon' },
    })

    expect(wrapper.find('.icon-mock').attributes('data-testid')).toBe('item-icon')
  })
})
