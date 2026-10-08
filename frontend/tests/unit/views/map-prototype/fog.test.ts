import { describe, expect, it } from 'vitest'
import { isExplored, isVisible, revealDisc } from '@/core/views/map-prototype/fog'

const WIDTH = 80
const HEIGHT = 80

describe('fog', () => {
  it('reveals a disc around the target tile', () => {
    const explored = new Uint8Array(WIDTH * HEIGHT)
    revealDisc(explored, WIDTH, HEIGHT, 40, 40, 5)
    expect(isExplored(explored, WIDTH, HEIGHT, 40, 40)).toBe(true)
    expect(isExplored(explored, WIDTH, HEIGHT, 44, 40)).toBe(true)
    expect(isExplored(explored, WIDTH, HEIGHT, 40, 44)).toBe(true)
    expect(isExplored(explored, WIDTH, HEIGHT, 46, 40)).toBe(false)
    expect(isExplored(explored, WIDTH, HEIGHT, 10, 10)).toBe(false)
  })

  it('clips the disc at map bounds without throwing', () => {
    const explored = new Uint8Array(WIDTH * HEIGHT)
    revealDisc(explored, WIDTH, HEIGHT, 0, 0, 8)
    expect(isExplored(explored, WIDTH, HEIGHT, 0, 0)).toBe(true)
    expect(isExplored(explored, WIDTH, HEIGHT, 5, 0)).toBe(true)
    expect(isExplored(explored, WIDTH, HEIGHT, 79, 79)).toBe(false)
  })

  it('is idempotent and additive across reveals', () => {
    const explored = new Uint8Array(WIDTH * HEIGHT)
    revealDisc(explored, WIDTH, HEIGHT, 20, 20, 4)
    const afterFirst = explored.slice()
    revealDisc(explored, WIDTH, HEIGHT, 20, 20, 4)
    expect(explored).toEqual(afterFirst)
    revealDisc(explored, WIDTH, HEIGHT, 60, 60, 4)
    expect(isExplored(explored, WIDTH, HEIGHT, 20, 20)).toBe(true)
    expect(isExplored(explored, WIDTH, HEIGHT, 60, 60)).toBe(true)
    expect(isExplored(explored, WIDTH, HEIGHT, 40, 40)).toBe(false)
  })

  it('reports out-of-bounds tiles as unexplored', () => {
    const explored = new Uint8Array(WIDTH * HEIGHT)
    expect(isExplored(explored, WIDTH, HEIGHT, -1, 0)).toBe(false)
    expect(isExplored(explored, WIDTH, HEIGHT, 0, 80)).toBe(false)
    expect(isExplored(explored, WIDTH, HEIGHT, 80, 0)).toBe(false)
  })

  it('isVisible follows the explored mask unless inspection is bypassed', () => {
    const explored = new Uint8Array(WIDTH * HEIGHT)
    revealDisc(explored, WIDTH, HEIGHT, 10, 10, 3)
    expect(isVisible(explored, WIDTH, HEIGHT, 10, 10)).toBe(true)
    expect(isVisible(explored, WIDTH, HEIGHT, 40, 40)).toBe(false)
    expect(isVisible(explored, WIDTH, HEIGHT, 40, 40, true)).toBe(true)
  })
})
