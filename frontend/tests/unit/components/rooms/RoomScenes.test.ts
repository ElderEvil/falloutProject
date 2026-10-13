import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { getRoomDetailScene, ARENA_DETAIL_SCENE } from '@/modules/rooms/models/roomScenes'
import { getRoomImageUrl } from '@/core/utils/image'
import RoomPreviewSection from '@/modules/rooms/components/RoomPreviewSection.vue'

const arena = { name: 'Arena', category: 'arena', tier: 1 }

describe('room detail scene roles', () => {
  it('uses the curated Arena scene for supported tiers and falls back for unknown catalog entries', () => {
    for (const tier of [1, 2, 3])
      expect(getRoomDetailScene({ ...arena, tier })).toBe(ARENA_DETAIL_SCENE)
    expect(getRoomDetailScene({ ...arena, tier: 4 })).toBeNull()
    expect(getRoomDetailScene({ ...arena, category: 'production' })).toBeNull()
    expect(getRoomDetailScene({ ...arena, name: 'Power Generator' })).toBeNull()
    expect(getRoomDetailScene(null)).toBeNull()
  })

  it('records actual WebP encoding, dimensions and unobstructed actor anchors', () => {
    const bytes = readFileSync('public/assets/room-scenes/arena-industrial-v1.webp')
    expect(bytes.toString('ascii', 0, 4)).toBe('RIFF')
    expect(bytes.toString('ascii', 8, 12)).toBe('WEBP')
    expect(bytes.toString('ascii', 12, 16)).toBe('VP8 ')
    expect(bytes.readUInt16LE(26) & 0x3fff).toBe(1536)
    expect(bytes.readUInt16LE(28) & 0x3fff).toBe(1024)
    const manifest = JSON.parse(readFileSync('public/assets/room-scenes/manifest.json', 'utf8'))
    expect(manifest.assets[0].actor_anchors).toEqual([
      [0.35, 0.8],
      [0.65, 0.8],
    ])
  })

  it('shows grid art after a detail image error, then the existing empty placeholder after both fail', async () => {
    const wrapper = mount(RoomPreviewSection, {
      props: {
        roomName: 'Arena',
        roomImageUrl: ARENA_DETAIL_SCENE,
        imageUrl: '/static/grid.png',
        roomUnits: 6,
        dwellerCapacity: 2,
        assignedDwellers: [],
      },
    })
    expect(wrapper.find('img').attributes('src')).toBe(ARENA_DETAIL_SCENE)
    await wrapper.find('img').trigger('error')
    expect(wrapper.find('img').attributes('src')).toBe(getRoomImageUrl('/static/grid.png'))
    await wrapper.find('img').trigger('error')
    expect(wrapper.text()).toContain('No Image Available')
    await wrapper.setProps({ roomImageUrl: '/new-scene.webp' })
    expect(wrapper.find('img').attributes('src')).toBe('/new-scene.webp')
  })
})
