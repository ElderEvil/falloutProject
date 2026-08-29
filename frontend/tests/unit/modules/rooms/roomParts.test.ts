import { describe, expect, it } from 'vitest'
import {
  getRoomDetailParts,
  isOverseersOffice,
  isRadioRoom,
  isVaultDoor,
  producesResources,
  type RoomPart,
} from '@/modules/rooms/models/roomParts'
import type { Room } from '@/modules/rooms/models/room'

const room = (overrides: Partial<Room> = {}): Room =>
  ({
    id: 'room-1',
    name: 'Power Generator',
    category: 'production',
    ability: 'strength',
    tier: 1,
    ...overrides,
  }) as Room

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
    expect(names(parts)).toBe('preview,info,dwellerList,actions')
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
})
