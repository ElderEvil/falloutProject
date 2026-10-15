import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AssetGalleryView from '@/core/views/AssetGalleryView.vue'
import { apiGet } from '@/core/utils/api'

vi.mock('@/core/utils/api', () => ({ apiGet: vi.fn().mockResolvedValue([]) }))

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

it('keeps static previews available without requesting authenticated catalogs', async () => {
  const gallery = mount(AssetGalleryView)
  await flushPromises()
  expect(apiGet).not.toHaveBeenCalled()
  expect(gallery.findAll('img').map((image) => image.attributes('alt'))).toEqual([
    'Deathclaw',
    'Feral Ghoul',
    'Mole Rat',
    'Radscorpion',
    'Radroach',
    'Eyebot',
    'Protectron',
    'Mr. Handy',
  ])
  gallery.unmount()
})

it('filters the assembled previews and links to the corresponding original sheet', async () => {
  const gallery = mount(AssetGalleryView)
  await gallery.get('input').setValue('ghoul')
  const images = gallery.findAll('img')
  expect(images).toHaveLength(1)
  expect(images[0]?.attributes('src')).toContain('/creature_images/assembled/feral-ghoul.webp')
  expect(gallery.get('a').attributes('href')).toContain('/creature_images/feral-ghoul.png')
  gallery.unmount()
})

it('still loads authenticated catalogs when logged in', async () => {
  localStorage.setItem('token', 'test-token')
  const gallery = mount(AssetGalleryView)
  await flushPromises()
  expect(apiGet).toHaveBeenCalledTimes(4)
  gallery.unmount()
})
