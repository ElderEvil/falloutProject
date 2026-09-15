import { describe, expect, it } from 'vitest'
import {
  craftingItemType,
  getRoomDetailParts,
  isCraftingRoom,
  isElevator,
  isOverseersOffice,
  isRadioRoom,
  isTrainingRoom,
  isVaultDoor,
  producesResources,
  type RoomPart,
} from '@/modules/rooms/models/roomParts'
import type { Room } from '@/modules/rooms/models/room'
import type { Incident } from '@/modules/combat/models/incident'
import type { IncidentAftermath } from '@/modules/combat/models/incident'

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

describe('getRoomDetailParts', () => {
  it('returns no parts for a null room', () => {
    expect(getRoomDetailParts(null)).toEqual([])
  })

  it('renders only the arena part for arena rooms', () => {
    expect(getRoomDetailParts(room({ name: 'Arena', category: 'arena' }))).toEqual(['arena'])
  })

  it('renders production stats for producing rooms', () => {
    const parts = getRoomDetailParts(room())
    expect(names(parts)).toBe('preview,info,productionStats,dwellerList,actions')
  })

  it('omits production stats when a production room has no ability', () => {
    const parts = getRoomDetailParts(room({ ability: null }))
    expect(parts).not.toContain('productionStats')
  })

  it('omits production stats for non-production rooms', () => {
    const parts = getRoomDetailParts(room({ category: 'training', name: 'Strength Room' }))
    expect(names(parts)).toBe('preview,info,training,dwellerList,actions')
  })

  it('renders radio stats and controls for radio rooms', () => {
    const parts = getRoomDetailParts(room({ name: 'Radio Studio', category: 'misc.', ability: 'charisma' }))
    expect(names(parts)).toBe('preview,info,radioStats,dwellerList,actions,radioControls')
  })

  it('renders the briefing for the Overseer’s Office', () => {
    const parts = getRoomDetailParts(room({ name: "Overseer's Office", category: 'misc.', ability: null }))
    expect(names(parts)).toBe('preview,info,overseerBriefing,dwellerList,actions')
  })

  it('renders no production stats for the vault door', () => {
    const parts = getRoomDetailParts(room({ name: 'Vault Door', category: 'misc.', ability: null }))
    expect(names(parts)).toBe('preview,info,dwellerList,actions')
  })

  it('renders the crafting panel for workshop rooms', () => {
    const parts = getRoomDetailParts(room({ name: 'Weapon workshop', category: 'crafting', ability: null }))
    expect(names(parts)).toBe('preview,info,crafting,dwellerList,actions')
  })

  it('omits crafting for crafting rooms that are not workshops', () => {
    const parts = getRoomDetailParts(room({ name: 'Mystery bench', category: 'crafting', ability: null }))
    expect(parts).not.toContain('crafting')
  })

  it('replaces every generic section with the overlay while an incident is live', () => {
    expect(getRoomDetailParts(room(), incident())).toEqual(['incident'])
  })

  it('keeps arena precedence over a live incident', () => {
    expect(getRoomDetailParts(room({ name: 'Arena', category: 'arena' }), incident())).toEqual(['arena'])
  })

  it('renders the generic sections when no incident is live', () => {
    expect(names(getRoomDetailParts(room(), null))).toBe('preview,info,productionStats,dwellerList,actions')
  })

  it('shows the aftermath instead of the generic sections once an incident is over', () => {
    expect(getRoomDetailParts(room(), null, aftermath())).toEqual(['aftermath'])
  })

  it('keeps a live incident ahead of an unresolved aftermath', () => {
    expect(getRoomDetailParts(room(), incident(), aftermath())).toEqual(['incident'])
  })

  it('keeps arena precedence over an aftermath', () => {
    expect(getRoomDetailParts(room({ name: 'Arena', category: 'arena' }), null, aftermath())).toEqual([
      'arena',
    ])
  })
})

describe('special room predicates', () => {
  it('matches radio rooms by name', () => {
    expect(isRadioRoom(room({ name: 'Radio Studio' }))).toBe(true)
    expect(isRadioRoom(room({ name: 'Power Generator' }))).toBe(false)
    expect(isRadioRoom(null)).toBe(false)
  })

  it('matches the vault door exactly', () => {
    expect(isVaultDoor(room({ name: 'Vault Door' }))).toBe(true)
    expect(isVaultDoor(room({ name: 'Vault Doorway' }))).toBe(false)
    expect(isVaultDoor(null)).toBe(false)
  })

  it('matches the Overseer’s Office exactly', () => {
    expect(isOverseersOffice(room({ name: "Overseer's Office" }))).toBe(true)
    expect(isOverseersOffice(room({ name: 'Overseer Office' }))).toBe(false)
    expect(isOverseersOffice(null)).toBe(false)
  })

  it('detects producing rooms', () => {
    expect(producesResources(room())).toBe(true)
    expect(producesResources(room({ ability: null }))).toBe(false)
    expect(producesResources(room({ category: 'training' }))).toBe(false)
    expect(producesResources(null)).toBe(false)
  })

  it('detects training rooms', () => {
    expect(isTrainingRoom(room({ category: 'training' }))).toBe(true)
    expect(isTrainingRoom(room({ category: 'TRAINING' }))).toBe(true)
    expect(isTrainingRoom(room())).toBe(false)
    expect(isTrainingRoom(null)).toBe(false)
  })

  it('matches elevators exactly', () => {
    expect(isElevator(room({ name: 'Elevator' }))).toBe(true)
    expect(isElevator(room({ name: 'Elevators' }))).toBe(false)
    expect(isElevator(null)).toBe(false)
  })
})

describe('craftingItemType', () => {
  it('maps each workshop name to its catalog', () => {
    expect(craftingItemType(room({ name: 'Weapon workshop', category: 'crafting', ability: null }))).toBe('weapon')
    expect(craftingItemType(room({ name: 'Outfit workshop', category: 'crafting', ability: null }))).toBe('outfit')
  })

  it('returns null outside a recognised workshop', () => {
    expect(craftingItemType(room())).toBeNull()
    expect(craftingItemType(room({ name: 'Mystery bench', category: 'crafting', ability: null }))).toBeNull()
    expect(craftingItemType(null)).toBeNull()
  })

  it('detects crafting rooms', () => {
    expect(isCraftingRoom(room({ category: 'crafting' }))).toBe(true)
    expect(isCraftingRoom(room())).toBe(false)
    expect(isCraftingRoom(null)).toBe(false)
  })
})
