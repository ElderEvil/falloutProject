import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vite-plus/test'

/**
 * The room preview frame's height comes from `aspect-ratio`, and Firefox
 * resolves container-query length units against the viewport until that frame
 * is laid out. Sizing the dweller slots with `cqh` therefore painted oversized
 * portraits and silhouettes for several frames on modal open. Slots now size
 * from the frame height with percentages; container units must not return.
 */
const PREVIEW_FILES = [
  'src/modules/rooms/components/RoomPreviewSection.vue',
  'src/modules/rooms/components/RoomDwellerSlot.vue',
]

const CONTAINER_UNIT = /(?<!\w)\d*\.?\d+cq(?:h|w|i|b|min|max)\b/i
const CONTAINER_DECLARATION = /container-type\s*:\s*(?:size|inline-size)/i
const PORTRAIT_RATIO_TOKEN = 'var(--portrait-frame-aspect'
const PORTRAIT_RATIO_DECLARATION = '--portrait-frame-aspect:'

describe('room preview sizing', () => {
  it('detects negative and uppercase container-query units', () => {
    expect('-1cqh').toMatch(CONTAINER_UNIT)
    expect('1CQH').toMatch(CONTAINER_UNIT)
    expect('var(--spacing)').not.toMatch(CONTAINER_UNIT)
  })

  it.each(PREVIEW_FILES)('%s does not size with container-query units', (file) => {
    const source = readFileSync(join(process.cwd(), file), 'utf8')
    expect(source).not.toMatch(CONTAINER_UNIT)
    expect(source).not.toMatch(CONTAINER_DECLARATION)
  })

  it('keeps the portrait ratio parent-owned instead of hardcoded in the slot', () => {
    const frame = readFileSync(
      join(process.cwd(), 'src/modules/rooms/components/RoomPreviewSection.vue'),
      'utf8'
    )
    const slot = readFileSync(
      join(process.cwd(), 'src/modules/rooms/components/RoomDwellerSlot.vue'),
      'utf8'
    )
    expect(frame).toContain(PORTRAIT_RATIO_DECLARATION)
    expect(slot).toContain(PORTRAIT_RATIO_TOKEN)
    // A literal ratio in the slot would silently override a taller/portrait frame.
    expect(slot).not.toMatch(/aspect-ratio:\s*2\s*\/\s*3\s*;/)
  })
})
