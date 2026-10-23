import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vite-plus/test'
import {
  AMBIENCE_MANIFEST,
  ROOM_AMBIENCE_MANIFEST,
  getAmbienceSrc,
  getRoomAmbienceKey,
} from '@/core/audio/soundManifest'

describe('getRoomAmbienceKey', () => {
  it('prefers the per-room loop over the category loop', () => {
    expect(getRoomAmbienceKey({ name: 'Power Generator', category: 'PRODUCTION' })).toBe(
      'power generator'
    )
  })

  it('ignores case and surrounding whitespace', () => {
    expect(getRoomAmbienceKey({ name: '  Classroom  ', category: 'training' })).toBe('classroom')
  })

  it('falls back to the category loop for a room with no per-room loop', () => {
    expect(getRoomAmbienceKey({ name: 'Broom Closet', category: 'Training' })).toBe('training')
  })

  it('returns undefined when neither the room nor the category is mapped', () => {
    expect(getRoomAmbienceKey({ name: 'Broom Closet', category: 'storage' })).toBeUndefined()
  })

  it('returns undefined for a missing room', () => {
    expect(getRoomAmbienceKey(null)).toBeUndefined()
    expect(getRoomAmbienceKey(undefined)).toBeUndefined()
  })
})

describe('getAmbienceSrc', () => {
  it('resolves a per-room key', () => {
    expect(getAmbienceSrc('armory')).toBe('/audio/ambience/armory.mp3')
  })

  it('resolves a category key', () => {
    expect(getAmbienceSrc('training')).toBe(AMBIENCE_MANIFEST.training)
  })
})

it('gives every room in the backend catalog a per-room loop', () => {
  const catalogPath = resolve('..', 'backend', 'app', 'data', 'vault', 'rooms.json')
  expect(existsSync(catalogPath), `Missing room catalog: ${catalogPath}`).toBe(true)

  const rooms: { name: string; category: string }[] = JSON.parse(readFileSync(catalogPath, 'utf8'))
  const uncovered = rooms
    .filter((room) => !(room.name.trim().toLowerCase() in ROOM_AMBIENCE_MANIFEST))
    .map((room) => room.name)

  expect(uncovered).toEqual([])
  expect(Object.keys(ROOM_AMBIENCE_MANIFEST)).toHaveLength(rooms.length)
})
