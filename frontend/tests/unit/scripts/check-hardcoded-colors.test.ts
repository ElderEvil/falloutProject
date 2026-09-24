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

  it('flags modern CSS color functions', () => {
    expect(findHardcodedColors('.a { color: oklch(70% 0.15 200); }')).toEqual([
      'oklch(70% 0.15 200)',
    ])
    expect(findHardcodedColors('.a { color: lab(50% 40 30); }')).toEqual(['lab(50% 40 30)'])
    expect(findHardcodedColors('.a { color: lch(50% 40 30); }')).toEqual(['lch(50% 40 30)'])
    expect(findHardcodedColors('.a { color: color(display-p3 1 0.5 0); }')).toEqual([
      'color(display-p3 1 0.5 0)',
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

  it('flags literal channels even when the alpha comes from a token', () => {
    expect(findHardcodedColors('.a { background: rgb(34 197 94 / var(--opacity)); }')).toEqual([
      'rgb(34 197 94 / var(--opacity))',
    ])
    expect(findHardcodedColors('.a { background: rgba(34, 197, 94, var(--opacity)); }')).toEqual([
      'rgba(34, 197, 94, var(--opacity))',
    ])
  })

  it('allows neutral black and white scrims, with or without alpha', () => {
    expect(findHardcodedColors('.a { background: rgba(0, 0, 0, 0.5); }')).toEqual([])
    expect(findHardcodedColors('.a { background: rgb(0 0 0 / 0.3); }')).toEqual([])
    expect(findHardcodedColors('.a { color: #ffffff; }')).toEqual([])
    expect(findHardcodedColors('.a { background: rgb(255 255 255 / 0.02); }')).toEqual([])
    expect(findHardcodedColors('.a { background: #00000080; }')).toEqual([])
    expect(findHardcodedColors('.a { background: #0008; }')).toEqual([])
    expect(findHardcodedColors('.a { background: #fff4; }')).toEqual([])
    expect(findHardcodedColors('.a { background: #ffffff80; }')).toEqual([])
    expect(findHardcodedColors('.a { background: #000000); }')).toEqual([])
  })

  it('still flags non-neutral alpha hex colors', () => {
    expect(findHardcodedColors('.a { background: #ff00aa80; }')).toEqual(['#ff00aa80'])
    expect(findHardcodedColors('.a { background: #0f08; }')).toEqual(['#0f08'])
  })
})
