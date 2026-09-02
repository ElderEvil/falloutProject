import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('index.html', () => {
  it('does not hint TypeScript source files as production resources', () => {
    const indexHtml = readFileSync(resolve(import.meta.dirname, '../../index.html'), 'utf8')

    expect(indexHtml).not.toMatch(/<link\b[^>]+href=["'][^"']+\.ts["']/)
  })
})
