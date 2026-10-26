import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import gridImages from '@/modules/rooms/models/roomGridImages.json'
import {
  getRoomDetailScene,
  getRoomGridScene,
  ARENA_DETAIL_SCENES,
  RESPONSE_DETAIL_SCENES,
} from '@/modules/rooms/models/roomScenes'
import { getRoomImageUrl } from '@/core/utils/image'
import RoomPreviewSection from '@/modules/rooms/components/RoomPreviewSection.vue'
import RoomGridCell from '@/modules/rooms/components/RoomGridCell.vue'
import type { Room } from '@/modules/rooms/models/room'

const arena = { name: 'Arena', category: 'arena', tier: 1 }

const arenaRoom = (tier: number) =>
  ({
    ...arena,
    tier,
    id: 'arena-1',
    size: 6,
    size_min: 6,
    image_url: '/static/room_images/arena.webp',
  }) as Room

const mountGridCell = (room: Room) =>
  mount(RoomGridCell, {
    props: {
      room,
      showRoomImages: true,
      isPowerOutage: false,
      selected: false,
      isDraggingOver: false,
      highlighted: false,
      merged: false,
    },
    global: {
      stubs: { RoomDwellers: true, TooltipLabel: { template: '<div><slot /></div>' } },
    },
  })

describe('room detail scene roles', () => {
  it('ships every grid variant under a filename matching its content hash', () => {
    for (const url of Object.values(gridImages)) {
      const bytes = readFileSync(`public${url}`)
      const hash = createHash('sha256').update(bytes).digest('hex').slice(0, 16)
      expect(url).toBe(`/assets/room-grid/${hash}.webp`)
      expect(bytes.toString('ascii', 8, 12)).toBe('WEBP')
    }
  })

  it('ships compact WebP grid artwork for the LCP image and curated scenes', () => {
    for (const room of [
      arenaRoom(1),
      {
        ...arenaRoom(1),
        name: 'Vault Door',
        category: 'misc',
        image_url: '/static/room_images/Vault Door Adv.png',
      },
    ]) {
      const url = getRoomGridScene(room)
      expect(url).toMatch(/^\/assets\/room-grid\/.+\.webp$/)
      const bytes = readFileSync(`public${url}`)
      expect(bytes.toString('ascii', 8, 12)).toBe('WEBP')
      expect(bytes.length).toBeLessThan(40000)
      expect(bytes.readUInt16LE(26) & 0x3fff).toBeLessThanOrEqual(768)
    }
  })

  it('keeps unknown room artwork on its existing URL', () => {
    expect(
      getRoomGridScene({
        ...arenaRoom(1),
        name: 'Custom',
        category: 'custom',
        image_url: '/static/custom.png',
      })
    ).toBeNull()
  })

  it.each([3, 6, 9])('renders the response room artwork at footprint %i', (size) => {
    const room = {
      ...arenaRoom(1),
      name: 'Response Station',
      category: 'response',
      size,
      size_min: 3,
      image_url: `/static/room_images/response-bay-size-${size}.webp`,
    } as Room
    expect(getRoomDetailScene(room)).toBe(RESPONSE_DETAIL_SCENES[size])
    expect(mountGridCell(room).get('img').attributes('src')).toBe(getRoomGridScene(room))
  })

  it.each([3, 6, 9])(
    'ships size-%i artwork at its native footprint ratio with matching fallback',
    (size) => {
      const bytes = readFileSync(`public${RESPONSE_DETAIL_SCENES[size]}`)
      expect(bytes.toString('ascii', 0, 4)).toBe('RIFF')
      expect(bytes.toString('ascii', 8, 12)).toBe('WEBP')
      expect(bytes.readUInt16LE(26) & 0x3fff).toBe((724 * size) / 3)
      expect(bytes.readUInt16LE(28) & 0x3fff).toBe(724)
      expect(
        bytes.equals(
          readFileSync(`../backend/app/static/room_images/response-bay-size-${size}.webp`)
        )
      ).toBe(true)
    }
  )

  it.each([1, 2, 3])('uses compact Arena artwork in the grid at tier %i', (tier) => {
    const room = arenaRoom(tier)
    expect(mountGridCell(room).get('img').attributes('src')).toBe(getRoomGridScene(room))
  })

  it('uses the curated Arena scene for supported tiers and falls back for unknown catalog entries', () => {
    for (const tier of [1, 2, 3])
      expect(getRoomDetailScene({ ...arena, tier })).toBe(ARENA_DETAIL_SCENES[tier])
    expect(new Set([1, 2, 3].map((tier) => getRoomDetailScene({ ...arena, tier })))).toHaveProperty(
      'size',
      3
    )
    expect(getRoomDetailScene({ ...arena, tier: 4 })).toBeNull()
    expect(getRoomDetailScene({ ...arena, category: 'production' })).toBeNull()
    expect(getRoomDetailScene({ ...arena, name: 'Power Generator' })).toBeNull()
    expect(getRoomDetailScene(null)).toBeNull()
  })

  it.each([1, 2, 3])('records valid tier-%i art and matching manifest metadata', (tier) => {
    const path = ARENA_DETAIL_SCENES[tier]
    const bytes = readFileSync(`public${path}`)
    expect(bytes.toString('ascii', 0, 4)).toBe('RIFF')
    expect(bytes.toString('ascii', 8, 12)).toBe('WEBP')
    expect(bytes.toString('ascii', 12, 16)).toBe('VP8 ')
    const manifest = JSON.parse(readFileSync('public/assets/room-scenes/manifest.json', 'utf8'))
    const asset = manifest.assets.find((entry: { path: string }) => entry.path === path)
    expect(asset.tiers).toEqual([tier])
    expect(asset.width / asset.height).toBe(3)
    expect(asset.safe_crop).toEqual([0, 0, 1, 1])
    expect(bytes.readUInt16LE(26) & 0x3fff).toBe(asset.width)
    expect(bytes.readUInt16LE(28) & 0x3fff).toBe(asset.height)
    expect(asset.actor_anchors).toEqual([
      [0.35, 0.8],
      [0.65, 0.8],
    ])
  })

  it('shows grid art after a detail image error, then the existing empty placeholder after both fail', async () => {
    const wrapper = mount(RoomPreviewSection, {
      props: {
        roomName: 'Arena',
        roomImageUrl: ARENA_DETAIL_SCENES[1],
        imageUrl: '/static/grid.png',
        roomUnits: 6,
        dwellerCapacity: 2,
        assignedDwellers: [],
      },
    })
    expect(wrapper.find('img').attributes('src')).toBe(ARENA_DETAIL_SCENES[1])
    await wrapper.find('img').trigger('error')
    expect(wrapper.find('img').attributes('src')).toBe(getRoomImageUrl('/static/grid.png'))
    await wrapper.find('img').trigger('error')
    expect(wrapper.text()).toContain('No Image Available')
    await wrapper.setProps({ roomImageUrl: '/new-scene.webp' })
    expect(wrapper.find('img').attributes('src')).toBe('/new-scene.webp')
  })

  it('falls back through the grid sprite and then hides the image in a room grid cell', async () => {
    const wrapper = mountGridCell(arenaRoom(1))
    expect(wrapper.get('img').attributes('src')).toBe(getRoomGridScene(arenaRoom(1)))
    await wrapper.get('img').trigger('error')
    expect(wrapper.get('img').attributes('src')).toBe(ARENA_DETAIL_SCENES[1])
    await wrapper.get('img').trigger('error')
    expect(wrapper.get('img').attributes('src')).toBe(
      getRoomImageUrl('/static/room_images/arena.webp')
    )
    await wrapper.get('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
  })
})
