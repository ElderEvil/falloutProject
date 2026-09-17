import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const SRC = join(process.cwd(), 'src')

function styleSources(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry)
    if (statSync(path).isDirectory()) return styleSources(path)
    return /\.(vue|css)$/.test(path) ? [path] : []
  })
}

describe('style guidelines', () => {
  // `transition: all` also animates layout and paint properties nobody chose, and the
  // formatter cannot catch it. Guarded here so a stray one fails the suite.
  it('lists the transitioned properties instead of using all', () => {
    const offenders = styleSources(SRC)
      .filter((file) => /transition:\s*all\b/.test(readFileSync(file, 'utf-8')))
      .map((file) => file.slice(SRC.length + 1))

    expect(offenders).toEqual([])
  })
})
