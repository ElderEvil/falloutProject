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

const CONTAINER_UNIT = /(?<![\w-])\d*\.?\d+cq(?:h|w|i|b|min|max)\b/
const CONTAINER_DECLARATION = /container-type\s*:\s*(?:size|inline-size)/

describe('room preview sizing', () => {
  it.each(PREVIEW_FILES)('%s does not size with container-query units', (file) => {
    const source = readFileSync(join(process.cwd(), file), 'utf8')
    expect(source).not.toMatch(CONTAINER_UNIT)
    expect(source).not.toMatch(CONTAINER_DECLARATION)
  })
})
