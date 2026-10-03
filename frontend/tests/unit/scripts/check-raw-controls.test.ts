import { describe, expect, it } from 'vitest'
import { findRawControls, isInScope } from '../../../scripts/check-raw-controls.mjs'

describe('check-raw-controls', () => {
  it('flags raw controls that have a vendored primitive', () => {
    expect(findRawControls('<template><button>Go</button></template>')).toEqual(['button'])
    expect(findRawControls('<template><select><option /></select></template>')).toEqual(['select'])
    expect(findRawControls('<template><input type="text" /></template>')).toEqual(['input'])
  })

  it('flags every occurrence, not just the first', () => {
    expect(
      findRawControls('<template><button /><button /><input /></template>')
    ).toEqual(['button', 'button', 'input'])
  })

  it('exempts controls whose primitive is not vendored yet', () => {
    expect(findRawControls('<template><textarea /></template>')).toEqual([])
    expect(findRawControls('<template><table><tr><td /></tr></table></template>')).toEqual([])
  })

  it('ignores markup outside the template block', () => {
    expect(findRawControls('<script>const tag = "<button>"</script>')).toEqual([])
    expect(findRawControls('<style>.x { content: "<select>"; }</style>')).toEqual([])
  })

  it('ignores commented-out controls', () => {
    expect(findRawControls('<template><!-- <button /> --><select /></template>')).toEqual(['select'])
  })

  it('ignores PascalCase component usage (shared primitives, not native controls)', () => {
    expect(findRawControls('<template><Button>Go</Button></template>')).toEqual([])
    expect(findRawControls('<template><Button /><Input /><Select /></template>')).toEqual([])
  })

  it('returns nothing for a file with no template', () => {
    expect(findRawControls('export default { name: "X" }')).toEqual([])
  })

  it('scopes to src/modules and not look-alike siblings', () => {
    expect(isInScope('src/modules/chat/components/DwellerChat.vue')).toBe(true)
    expect(isInScope('src/modulesX/thing.vue')).toBe(false)
    expect(isInScope('src/core/components/ui/button/Button.vue')).toBe(false)
    expect(isInScope('src/modules')).toBe(false)
  })
})
