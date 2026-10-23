import boostedRooms from './boosted-rooms.json' with { type: 'json' }
import type { components } from '../../src/core/types/api.generated'

type TrainingRead = components['schemas']['TrainingRead']

const vault = {
  id: 'vault-perf',
  number: 42,
  bottle_caps: 1250,
  happiness: 82,
  power: 80,
  power_max: 100,
  food: 70,
  food_max: 100,
  water: 80,
  water_max: 100,
  population_max: 20,
  radio_mode: 'recruitment',
  created_at: '2026-08-22T00:00:00Z',
  updated_at: '2026-08-22T00:00:00Z',
  resource_warnings: [],
  room_count: 2,
  dweller_count: 2,
  stimpack: 4,
  radaway: 2,
}

const rooms = [
  {
    id: 'power-room',
    vault_id: vault.id,
    name: 'Power Generator',
    category: 'production',
    ability: 'strength',
    tier: 1,
    capacity: 2,
    size: 3,
    size_min: 3,
    size_max: 3,
    coordinate_x: 0,
    coordinate_y: 3,
    image_url: null,
    t2_upgrade_cost: 500,
    t3_upgrade_cost: 1500,
  },
  {
    id: 'water-room',
    vault_id: vault.id,
    name: 'Water Treatment',
    category: 'production',
    ability: 'perception',
    tier: 1,
    capacity: 2,
    size: 3,
    size_min: 3,
    size_max: 3,
    coordinate_x: 7,
    coordinate_y: 3,
    image_url: null,
    t2_upgrade_cost: 500,
    t3_upgrade_cost: 1500,
  },
]

const dweller = {
  id: 'c0123456-0000-4000-8000-000000000001',
  vault_id: vault.id,
  first_name: 'Ada',
  last_name: 'Wells',
  thumbnail_url: '/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp',
  image_url: '/static/dweller_images/base/FOS_Dw_Default_Human_Female.webp',
  is_default_portrait: true,
  level: 4,
  health: 100,
  max_health: 100,
  radiation: 0,
  happiness: 90,
  room_id: 'power-room',
  status: 'working',
  age_group: 'adult',
  gender: 'female',
  rarity: 'common',
  experience: 120,
  age: 25,
  is_dead: false,
  visual_attributes: { race: 'human' },
  weapon: null,
  outfit: null,
  pet: null,
  strength: 5,
  perception: 6,
  endurance: 5,
  charisma: 4,
  intelligence: 7,
  agility: 6,
  luck: 4,
}

export type FixtureDweller = Omit<typeof dweller, 'room_id'> & { room_id: string | null }
export interface FixtureRoom {
  id: string
  vault_id: string
  name: string
  category: string
  ability: string | null
  tier: number
  capacity: number | null
  size: number
  size_min: number
  size_max: number
  coordinate_x: number
  coordinate_y: number
  image_url: string | null
  t2_upgrade_cost: number | null
  t3_upgrade_cost: number | null
}

export interface VaultFixture {
  name: 'small' | 'large'
  vault: typeof vault
  rooms: FixtureRoom[]
  roster: FixtureDweller[]
  trainings: TrainingRead[]
}

export function createSmallVault(): VaultFixture {
  return {
    name: 'small',
    vault: { ...vault },
    rooms: structuredClone(rooms),
    roster: [
      { ...dweller },
      {
        ...dweller,
        id: 'c0123456-0000-4000-8000-000000000002',
        first_name: 'Ben',
        last_name: 'Ortiz',
        room_id: null,
        status: 'idle',
      },
    ],
    trainings: [],
  }
}

// boosted-rooms.json is a snapshot of prepare_initial_rooms(..., is_boosted=True),
// with its three storage rooms fused as they are during seeding. Extra floors
// repeat the existing training, housing, and production blocks for a grown vault.
export function createLargeVault(): VaultFixture {
  const fixture = createSmallVault()
  fixture.name = 'large'
  fixture.rooms = boostedRooms.map((room, index) => ({
    ...room,
    id: `boosted-room-${index + 1}`,
    vault_id: vault.id,
  }))
  const trainingRooms = fixture.rooms.filter((room) => room.category === 'training')
  const productionRooms = fixture.rooms.filter((room) => room.category === 'production')
  const housing = fixture.rooms.find(
    (room) => room.name.toLowerCase() === 'living room' && room.size === 9
  )!
  const elevator = fixture.rooms.find((room) => room.name === 'Elevator')!
  for (const floor of [5, 6]) {
    fixture.rooms.push(
      ...trainingRooms.map((room) => ({
        ...room,
        id: `${room.id}-floor-${floor}`,
        coordinate_y: floor,
      }))
    )
  }
  fixture.rooms.push(
    ...[7, 16].map((x) => ({
      ...housing,
      id: `extra-housing-${x}`,
      coordinate_x: x,
      coordinate_y: 7,
    }))
  )
  fixture.rooms.push(
    ...productionRooms.map((room, index) => ({
      ...room,
      id: `${room.id}-floor-8`,
      coordinate_x: index === 0 ? 0 : 7 + (index - 1) * 3,
      coordinate_y: 8,
    }))
  )
  fixture.rooms.push(
    ...[5, 6, 7, 8].map((floor) => ({
      ...elevator,
      id: `extra-elevator-${floor}`,
      coordinate_y: floor,
    }))
  )
  const occupiedRooms = fixture.rooms
    .filter(
      (room) =>
        !['elevator', 'vault door', 'storage room', "overseer's office"].includes(
          room.name.toLowerCase()
        )
    )
    .sort((a, b) => Number(b.category === 'training') - Number(a.category === 'training'))
  const assignments = occupiedRooms
    .flatMap((room) => Array.from({ length: Math.ceil(room.size / 3) * 2 }, () => room))
    .slice(0, 100)
  if (assignments.length !== 100) throw new Error('Large fixture needs 100 valid room slots')
  fixture.roster = assignments.map((room, index) => {
    const gender = index % 2 === 0 ? 'Female' : 'Male'
    return {
      ...dweller,
      id: `c0123456-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
      first_name: `Resident ${String(index + 1).padStart(3, '0')}`,
      last_name: 'Vale',
      gender: gender.toLowerCase(),
      thumbnail_url: `/static/dweller_thumbnails/base/FOS_Dw_Default_Human_${gender}.webp`,
      image_url: `/static/dweller_images/base/FOS_Dw_Default_Human_${gender}.webp`,
      room_id: room.id,
      status:
        room.category === 'training'
          ? 'training'
          : room.name.toLowerCase() === 'living room'
            ? 'socializing'
            : 'working',
      level: 1 + (index % 50),
      happiness: 55 + (index % 46),
      health: 60 + (index % 30),
      radiation: (index % 4) * 2,
      strength: 3 + (index % 6),
      perception: 3 + ((index + 1) % 6),
      endurance: 3 + ((index + 2) % 6),
    }
  })
  const now = Date.now()
  fixture.trainings = fixture.roster
    .filter((resident) => resident.status === 'training')
    .map((resident, index) => {
      const room = fixture.rooms.find((room) => room.id === resident.room_id)!
      const stat = room.ability as TrainingRead['stat_being_trained']
      const progress = 10 + (index % 8) * 10
      const startedAt = new Date(now - (progress / 100) * 3600000).toISOString()
      return {
        id: `d0123456-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
        vault_id: vault.id,
        room_id: room.id,
        dweller_id: resident.id,
        status: 'active',
        stat_being_trained: stat,
        current_stat_value: resident[stat],
        target_stat_value: resident[stat] + 1,
        goal_stat_value: 10,
        progress,
        started_at: startedAt,
        estimated_completion_at: new Date(now + ((100 - progress) / 100) * 3600000).toISOString(),
        created_at: startedAt,
        updated_at: startedAt,
      }
    })
  fixture.vault = {
    ...vault,
    population_max: 100,
    dweller_count: fixture.roster.length,
    room_count: fixture.rooms.length,
    power: 900,
    power_max: 1000,
    food: 850,
    food_max: 1000,
    water: 875,
    water_max: 1000,
    bottle_caps: 250000,
  }
  return fixture
}
