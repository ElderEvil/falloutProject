import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ArenaRoomDetail from '@/modules/rooms/components/ArenaRoomDetail.vue'
import type { ArenaRoomState } from '@/modules/rooms/api/arena'

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const storeMock = vi.hoisted(() => {
  const readyRoom: ArenaRoomState = {
    room_id: 'arena-1',
    room_name: 'Arena',
    tier: 1,
    fighter_a_id: 'dweller-1',
    fighter_b_id: 'dweller-2',
    fighters: [
      {
        id: 'dweller-1',
        name: 'Alice Dweller',
        level: 10,
        health: 80,
        max_health: 100,
        power: 42,
        actor: {
          base_key: 'adult.vault_suit',
          variant_url: null,
          canvas_width: 1024,
          canvas_height: 1536,
          baseline_y: 1536,
          layers: [
            {
              slot: 'body',
              url: 'https://cdn.test/body.png',
              z: 10,
              anchor_x: 0,
              anchor_y: 0,
              width: 1024,
              height: 1536,
            },
          ],
        },
      },
      {
        id: 'dweller-2',
        name: 'Bravo Dweller',
        level: 8,
        health: 90,
        max_health: 100,
        power: 35,
        actor: null,
      },
    ],
    roster: [],
    fight_ready: true,
    match_done: false,
    fight_started: false,
    countdown_remaining: 0,
    can_start: true,
    winner_name: null,
    events: [],
  }
  return {
    currentRoom: readyRoom as ArenaRoomState | null,
    fetchState: vi.fn(),
    readyRoom,
  }
})

vi.mock('@/modules/rooms/stores/arena', () => ({
  useArenaStore: () => ({
    getRoom: () => storeMock.currentRoom,
    fetchState: storeMock.fetchState,
    setFighters: vi.fn(),
    startFight: vi.fn(),
    clearEvents: vi.fn(),
    reset: vi.fn(),
  }),
}))

const SCENE = {
  image_url: '/static/poc_v25/arena_empty.png',
  width: 1536,
  height: 1024,
  camera: 'side-on-2.5d',
  safe_crop: [0, 0, 1536, 1024],
  floor_baseline_y: 625,
  actor_slots: [
    { id: 'actor_a', x: 522, y: 625, facing: 'right', scale: 1 },
    { id: 'actor_b', x: 1014, y: 625, facing: 'left', scale: 1 },
  ],
}

const baseRoom = {
  id: 'arena-1',
  name: 'Arena',
  tier: 1,
  category: 'ARENA',
  ability: null,
  t2_upgrade_cost: 500,
  t3_upgrade_cost: 1000,
  detail_scene: SCENE,
}

const dwellers = [
  { id: 'dweller-1', first_name: 'Alice', last_name: 'Dweller', thumbnail_url: 'https://cdn.test/alice.png' },
  { id: 'dweller-2', first_name: 'Bravo', last_name: 'Dweller', thumbnail_url: 'https://cdn.test/bravo.png' },
]

const percent = (value: number, total: number) => `${(value / total) * 100}%`

const mountArena = (props: Record<string, unknown> = {}) =>
  mount(ArenaRoomDetail, {
    props: {
      room: baseRoom as never,
      vaultId: 'vault-1',
      assignedDwellers: dwellers as never,
      dwellerCapacity: 6,
      roomImageUrl: null,
      upgradeInfo: { canUpgrade: true, upgradeCost: 500, nextTier: 2, maxTier: 3 },
      isUpgrading: false,
      isDestroying: false,
      isVaultDoor: false,
      ...props,
    },
    global: {
      plugins: [createPinia()],
      stubs: {
        ArenaModal: { template: '<div class="battle-panel">Battle UI</div>' },
        RoomPreviewSection: { template: '<div class="room-preview-fallback" />' },
        ArenaActorSprite: {
          props: ['actor', 'portraitUrl', 'alt'],
          template:
            '<div class="actor-sprite" :data-actor="actor ? JSON.stringify(actor) : \'null\'" :data-portrait="portraitUrl" :data-alt="alt" />',
        },
      },
    },
  })

describe('ArenaRoomDetail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeMock.currentRoom = storeMock.readyRoom
    storeMock.fetchState.mockReset().mockResolvedValue(true)
  })

  it('fetches the arena state for the room on mount', async () => {
    const wrapper = mountArena()
    await flushPromises()

    expect(storeMock.fetchState).toHaveBeenCalledWith('vault-1', 'test-token')
    expect(wrapper.find('.arena-scene').exists()).toBe(true)
  })

  it('renders the scene image at the manifest intrinsic aspect ratio', async () => {
    const wrapper = mountArena()
    await flushPromises()

    const scene = wrapper.get('.arena-scene')
    expect(scene.attributes('style')).toContain('1536 / 1024')
    expect(wrapper.get('.arena-scene__image').attributes('src')).toBe(
      'http://localhost:8000/static/poc_v25/arena_empty.png'
    )
  })

  it('positions one sprite per slot at the slot percentages with feet anchoring and facing mirror', async () => {
    const wrapper = mountArena()
    await flushPromises()

    const slots = wrapper.findAll('.arena-scene__slot')
    expect(slots).toHaveLength(2)
    expect(slots[0].attributes('style')).toContain(`left: ${percent(522, 1536)}`)
    expect(slots[0].attributes('style')).toContain(`top: ${percent(625, 1024)}`)
    expect(slots[0].attributes('style')).toContain('translate(-50%, -100%) scaleX(1) scale(1)')
    expect(slots[1].attributes('style')).toContain(`left: ${percent(1014, 1536)}`)
    expect(slots[1].attributes('style')).toContain(`top: ${percent(625, 1024)}`)
    expect(slots[1].attributes('style')).toContain('translate(-50%, -100%) scaleX(-1) scale(1)')
  })

  it('passes the fighter actor payload to the sprite', async () => {
    const wrapper = mountArena()
    await flushPromises()

    const sprites = wrapper.findAll('.actor-sprite')
    expect(sprites).toHaveLength(2)
    expect(sprites[0].attributes('data-actor')).toBe(
      JSON.stringify(storeMock.readyRoom.fighters[0].actor)
    )
    expect(sprites[0].attributes('data-alt')).toBe('Alice Dweller')
  })

  it('maps slots by fighter_a_id/fighter_b_id, not the fighters array order', async () => {
    storeMock.currentRoom = {
      ...storeMock.readyRoom,
      fighters: [storeMock.readyRoom.fighters[1], storeMock.readyRoom.fighters[0]],
    }
    const wrapper = mountArena()
    await flushPromises()

    const sprites = wrapper.findAll('.actor-sprite')
    expect(sprites[0].attributes('data-alt')).toBe('Alice Dweller')
    expect(sprites[1].attributes('data-alt')).toBe('Bravo Dweller')
  })

  it('falls back to the dweller portrait when a fighter has no actor', async () => {
    const wrapper = mountArena()
    await flushPromises()

    const sprites = wrapper.findAll('.actor-sprite')
    expect(sprites[1].attributes('data-actor')).toBe('null')
    expect(sprites[1].attributes('data-portrait')).toBe('https://cdn.test/bravo.png')
    expect(sprites[1].attributes('data-alt')).toBe('Bravo Dweller')
  })

  it('renders the RoomPreviewSection fallback when detail_scene is absent', async () => {
    const wrapper = mountArena({ room: { ...baseRoom, detail_scene: null } as never })
    await flushPromises()

    expect(wrapper.find('.arena-scene').exists()).toBe(false)
    expect(wrapper.find('.room-preview-fallback').exists()).toBe(true)
  })

  it('uses the shared room-management section below the battle panel', async () => {
    const wrapper = mountArena()
    await flushPromises()

    expect(wrapper.text()).toContain('Battle UI')
    expect(wrapper.find('.room-management').text()).toContain('Management')
    expect(wrapper.text()).toContain('Upgrade to Tier 2')
    expect(wrapper.text()).toContain('Unassign All Dwellers')
    expect(wrapper.text()).toContain('Destroy Room')
  })
})
