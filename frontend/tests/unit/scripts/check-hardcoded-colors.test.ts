import { describe, expect, it } from 'vitest'
import { findHardcodedColors } from '../../../scripts/check-hardcoded-colors.mjs'

describe('check-hardcoded-colors', () => {
  it('flags hardcoded hex and functional colors', () => {
    expect(findHardcodedColors('.a { color: #ff00aa; }')).toEqual(['#ff00aa'])
    expect(findHardcodedColors('.a { color: rgb(34 197 94); }')).toEqual(['rgb(34 197 94)'])
    expect(findHardcodedColors('.a { background: rgba(12, 34, 56, 0.5); }')).toEqual([
      'rgba(12, 34, 56, 0.5)',
    ])
    expect(findHardcodedColors('.a { color: hsl(210, 50%, 40%); }')).toEqual([
      'hsl(210, 50%, 40%)',
    ])
  })

  it('allows design tokens, var() fallbacks, and token-derived relative colors', () => {
    expect(findHardcodedColors('.a { color: var(--color-theme-primary); }')).toEqual([])
    expect(findHardcodedColors('.a { color: var(--color-theme-primary, #00ff00); }')).toEqual([])
    expect(
      findHardcodedColors('.a { background: rgb(from var(--color-theme-primary) r g b / 0.2); }')
    ).toEqual([])
    expect(
      findHardcodedColors('.a { box-shadow: 0 0 8px rgba(var(--color-theme-primary-rgb), 0.3); }')
    ).toEqual([])
  })

  it('allows neutral black and white scrims', () => {
    expect(findHardcodedColors('.a { background: rgba(0, 0, 0, 0.5); }')).toEqual([])
    expect(findHardcodedColors('.a { background: rgb(0 0 0 / 0.3); }')).toEqual([])
    expect(findHardcodedColors('.a { color: #ffffff; }')).toEqual([])
    expect(findHardcodedColors('.a { background: rgb(255 255 255 / 0.02); }')).toEqual([])
  })
})
