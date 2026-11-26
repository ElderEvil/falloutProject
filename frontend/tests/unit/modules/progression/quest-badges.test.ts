import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vite-plus/test'
import { QUEST_TYPE_COLORS } from '@/modules/progression/models/quest'

/**
 * Quest badge readability contract.
 *
 * The palette lives in `src/assets/tailwind.css` and the class mapping in `QUEST_TYPE_COLORS`.
 * A badge is a bold uppercase 11-12px label, so its fill/ink pair must clear WCAG AA for small
 * text (4.5:1). The old `side` badge failed this contract in spirit rather than in ratio: it used
 * `--color-gray-800` with `text-theme-primary`, so it read as a disabled control and changed
 * appearance with the user's accent colour. These tests lock both properties.
 */

const THEME_CSS = readFileSync('src/assets/tailwind.css', 'utf8')

const INK = { 'text-black': '#000000', 'text-white': '#ffffff' } as const

function themeColor(name: string): string {
  const match = THEME_CSS.match(new RegExp(`--color-quest-${name}:\\s*(#[0-9a-fA-F]{6})`))
  if (!match) throw new Error(`--color-quest-${name} is not a literal hex in tailwind.css`)
  return match[1]!.toLowerCase()
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16))
  return 0.2126 * channel(r!) + 0.7152 * channel(g!) + 0.0722 * channel(b!)
}

function contrast(foreground: string, background: string): number {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return (light! + 0.05) / (dark! + 0.05)
}

describe('quest badge palette', () => {
  it('gives every type its own fill, never the user accent', () => {
    for (const [questType, colors] of Object.entries(QUEST_TYPE_COLORS)) {
      expect(colors.badge, `${questType} must not borrow the accent`).not.toContain('theme-primary')
      expect(colors.border, `${questType} must not borrow the accent`).not.toContain(
        'theme-primary'
      )
      expect(colors.badge, `${questType} needs an explicit ink`).toMatch(/text-(black|white)/)
      expect(colors.badge, `${questType} needs its own fill class`).toContain(
        `bg-quest-${questType}`
      )
    }
  })

  it('keeps every fill/ink pair at WCAG AA for small text', () => {
    for (const [questType, colors] of Object.entries(QUEST_TYPE_COLORS)) {
      const inkClass = colors.badge.match(/text-(black|white)/)?.[0] as keyof typeof INK
      const ratio = contrast(INK[inkClass], themeColor(questType))
      expect(
        ratio,
        `${questType}: ${inkClass} on --color-quest-${questType}`
      ).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('keeps cadence hues distinct so a type is not confused with another', () => {
    const fills = Object.keys(QUEST_TYPE_COLORS).map((questType) => themeColor(questType))
    expect(new Set(fills).size).toBe(fills.length)
  })
})
