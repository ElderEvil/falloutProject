import { describe, expect, it } from 'vite-plus/test'
import {
  craftingItemType,
  findProductionRoom,
  getRoomDetailParts,
  isBarbershop,
  isCraftingRoom,
  isElevator,
  isOverseersOffice,
  isRadioRoom,
  isResponseStation,
  isTrainingRoom,
  isVaultDoor,
  producesResources,
  type RoomPart,
} from '@/modules/rooms/models/roomParts'
import type { Room } from '@/modules/rooms/models/room'
import type { Incident, IncidentAftermath } from '@/modules/combat/models/incident'

const room = (overrides: Partial<Room> = {}): Room =>
  ({
    id: 'room-1',
    name: 'Power Generator',
    category: 'production',
    ability: 'strength',
    tier: 1,
    ...overrides,
  }) as Room

const incident = (overrides: Partial<Incident> = {}): Incident =>
  ({
    id: 'incident-1',
    room_id: 'room-1',
    type: 'raider_attack',
    family: 'intrusion',
    objective: 'defeat',
    ...overrides,
  }) as Incident

const aftermath = (overrides: Partial<IncidentAftermath> = {}): IncidentAftermath =>
  ({
    incidentId: 'incident-1',
    roomId: 'room-1',
    type: 'raider_attack',
    roomName: 'Power Generator',
    outcome: 'victory',
    capsEarned: 50,
    loot: null,
    enemiesDefeated: 3,
    damageDealt: 40,
    rounds: 6,
    ...overrides,
  }) as IncidentAftermath

const names = (parts: RoomPart[]) => parts.join(',')

const arena = () => room({ name: 'Arena', category: 'arena' })
const radio = () => room({ name: 'Radio Studio', category: 'misc.', ability: 'charisma' })
const workshop = () => room({ name: 'Weapon workshop', category: 'crafting', ability: null })

describe('getRoomDetailParts', () => {
  it('returns no parts for a null room', () => {
    expect(getRoomDetailParts(null)).toEqual([])
  })

  it.each([
    ['a producing room', room(), 'preview,info,productionStats,dwellerList,actions'],
    [
      'a training room',
      room({ category: 'training', name: 'Strength Room' }),
      'preview,info,training,dwellerList,actions',
    ],
    ['a radio room', radio(), 'preview,info,radioStats,dwellerList,actions,radioControls'],
    [
      'the Barbershop',
      room({ name: 'Barbershop', category: 'misc.', ability: 'charisma' }),
      'preview,info,barbershop,dwellerList,actions',
    ],
    [
      "the Overseer's Office",
      room({ name: "Overseer's Office", category: 'misc.', ability: null }),
      'preview,info,overseerBriefing,dwellerList,actions',
    ],
    [
      'the vault door',
      room({ name: 'Vault Door', category: 'misc.', ability: null }),
      'preview,info,dwellerList,actions',
    ],
    ['a workshop', workshop(), 'preview,info,crafting,dwellerList,actions'],
    [
      'a response room',
      room({ name: 'Response Station', category: 'response', ability: 'endurance' }),
      'preview,info,responseStation,dwellerList,actions',
    ],
  ])('renders the parts for %s', (_label, target, expected) => {
    expect(names(getRoomDetailParts(target))).toBe(expected)
  })

  it('renders only the arena part for arena rooms', () => {
    expect(getRoomDetailParts(arena())).toEqual(['arena'])
  })

  it.each([
    ['a production room without an ability', room({ ability: null }), 'productionStats'],
    [
      'a non-workshop crafting room',
      room({ name: 'Mystery bench', category: 'crafting', ability: null }),
      'crafting',
    ],
    ['another Misc. room', radio(), 'barbershop'],
  ])('omits a part that does not apply (%s)', (_label, target, part) => {
    expect(getRoomDetailParts(target)).not.toContain(part)
  })

  it('replaces every generic section with the overlay while an incident is live', () => {
    expect(getRoomDetailParts(room(), incident())).toEqual(['incident'])
  })

  it('keeps arena precedence over a live incident', () => {
    expect(getRoomDetailParts(arena(), incident())).toEqual(['arena'])
  })

  it('renders the generic sections when no incident is live', () => {
    expect(names(getRoomDetailParts(room(), null))).toBe(
      'preview,info,productionStats,dwellerList,actions'
    )
  })

  it('shows the aftermath instead of the generic sections once an incident is over', () => {
    expect(getRoomDetailParts(room(), null, aftermath())).toEqual(['aftermath'])
  })

  it('keeps a live incident ahead of an unresolved aftermath', () => {
    expect(getRoomDetailParts(room(), incident(), aftermath())).toEqual(['incident'])
  })

  it('keeps arena precedence over an aftermath', () => {
    expect(getRoomDetailParts(arena(), null, aftermath())).toEqual(['arena'])
  })

  it('adds maintenance only to Endurance storage rooms', () => {
    expect(getRoomDetailParts(room({ category: 'capacity', ability: 'endurance' }))).toContain(
      'storageMaintenance'
    )
    expect(getRoomDetailParts(room({ category: 'capacity', ability: 'charisma' }))).not.toContain(
      'storageMaintenance'
    )
  })
})

describe('special room predicates', () => {
  it.each([
    ['matches radio rooms by name', isRadioRoom, [room({ name: 'Radio Studio' })], [room()]],
    [
      'matches the Barbershop by exact name',
      isBarbershop,
      [room({ name: 'Barbershop' }), room({ name: 'barbershop' })],
      [room({ name: 'Barbershop supplies' }), room({ name: 'Radio Studio', category: 'misc.' })],
    ],
    [
      'matches the vault door exactly',
      isVaultDoor,
      [room({ name: 'Vault Door' })],
      [room({ name: 'Vault Doorway' })],
    ],
    [
      'matches the Overseer’s Office exactly',
      isOverseersOffice,
      [room({ name: "Overseer's Office" })],
      [room({ name: 'Overseer Office' })],
    ],
    [
      'detects producing rooms',
      producesResources,
      [room()],
      [room({ ability: null }), room({ category: 'training' })],
    ],
    [
      'detects training rooms regardless of case',
      isTrainingRoom,
      [room({ category: 'training' }), room({ category: 'TRAINING' })],
      [room()],
    ],
    [
      'matches elevators exactly',
      isElevator,
      [room({ name: 'Elevator' })],
      [room({ name: 'Elevators' })],
    ],
    [
      'detects response rooms by category, not name',
      isResponseStation,
      [room({ category: 'response', name: 'Response Station' }), room({ category: 'RESPONSE' })],
      [room({ category: 'production', name: 'Response Station' })],
    ],
  ])('%s', (_label, predicate, match, miss) => {
    for (const target of match) expect(predicate(target)).toBe(true)
    for (const target of miss) expect(predicate(target)).toBe(false)
  })

  it.each([
    ['isRadioRoom', isRadioRoom],
    ['isBarbershop', isBarbershop],
    ['isVaultDoor', isVaultDoor],
    ['isOverseersOffice', isOverseersOffice],
    ['producesResources', producesResources],
    ['isTrainingRoom', isTrainingRoom],
    ['isElevator', isElevator],
    ['isResponseStation', isResponseStation],
    ['isCraftingRoom', isCraftingRoom],
  ] as const)('%s rejects a missing room', (_name, predicate) => {
    expect(predicate(null)).toBe(false)
  })
})

describe('craftingItemType', () => {
  it.each([
    ['Weapon workshop', 'weapon'],
    ['Outfit workshop', 'outfit'],
  ])('maps %s to its catalog', (name, itemType) => {
    expect(craftingItemType(room({ name, category: 'crafting', ability: null }))).toBe(itemType)
  })

  it('returns null outside a recognised workshop', () => {
    expect(craftingItemType(room())).toBeNull()
    expect(
      craftingItemType(room({ name: 'Mystery bench', category: 'crafting', ability: null }))
    ).toBeNull()
    expect(craftingItemType(null)).toBeNull()
  })

  it('detects crafting rooms', () => {
    expect(isCraftingRoom(room({ category: 'crafting' }))).toBe(true)
    expect(isCraftingRoom(room())).toBe(false)
  })
})

describe('findProductionRoom', () => {
  it('maps each resource to its dedicated ability room', () => {
    const rooms = [
      room({ id: 'power-1', ability: 'strength' }),
      room({ id: 'food-1', name: 'Garden', ability: 'agility' }),
      room({ id: 'water-1', name: 'Water Treatment', ability: 'perception' }),
    ]

    expect(findProductionRoom(rooms, 'power')?.id).toBe('power-1')
    expect(findProductionRoom(rooms, 'food')?.id).toBe('food-1')
    expect(findProductionRoom(rooms, 'water')?.id).toBe('water-1')
  })

  it('falls back to an all-resource endurance room', () => {
    const rooms = [room({ id: 'all-1', name: 'Lounge', ability: 'endurance' })]

    expect(findProductionRoom(rooms, 'water')?.id).toBe('all-1')
  })
})
