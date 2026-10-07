import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Import-order guard for the shared test mocks (see tests/unit/helpers/mocks).
 *
 * The axios/router/iconify factories run when the mocked module is first
 * imported, so the helper module must already be evaluated: the helpers
 * import has to precede any import that can trigger evaluation of app code
 * or a mocked module. That means every static import form — single-line and
 * multiline, path (at-slash and relative) and bare (vue-router, iconify and
 * friends) — except the known-inert test runtimes themselves. Toast factory
 * calls happen at module scope and are order-independent, so only
 * axios/router/iconify factory calls are checked.
 */

const UNIT_TESTS_DIR = join(process.cwd(), 'tests/unit')
const SELF = 'architecture/mockImportOrderGuard.test.ts'
const FACTORY_CALL = /create(?:Axios|Router|Iconify|ApiClient)Mock\s*\(/
const IMPORT_RE = /^import\s+(?:[\s\S]*?\sfrom\s+)?['"]([^'"]+)['"]/gm
const HELPER_SOURCE_SUFFIX = 'helpers/mocks'
const INERT_SOURCE = /^(vitest|vue|pinia|@vue\/test-utils)(\/|$)/

function walkTestFiles(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      files.push(...walkTestFiles(full))
    } else if (entry.endsWith('.test.ts')) {
      files.push(full)
    }
  }
  return files
}

describe('mock helper import order', () => {
  it('imports helpers/mocks before any import that can trigger a mock factory', () => {
    const violations: string[] = []
    for (const file of walkTestFiles(UNIT_TESTS_DIR)) {
      const rel = relative(UNIT_TESTS_DIR, file).split('\\').join('/')
      if (rel === SELF) continue
      const source = readFileSync(file, 'utf8')
      if (!source.includes('vi.mock(') || !FACTORY_CALL.test(source)) continue
      const imports: { source: string; index: number }[] = []
      for (const match of source.matchAll(IMPORT_RE)) {
        imports.push({ source: match[1], index: match.index ?? 0 })
      }
      const helper = imports.find((imp) => imp.source.endsWith(HELPER_SOURCE_SUFFIX))
      const risky = imports.find(
        (imp) => !imp.source.endsWith(HELPER_SOURCE_SUFFIX) && !INERT_SOURCE.test(imp.source)
      )
      if (!helper || !risky || helper.index > risky.index) {
        violations.push(`${rel} (helpers/mocks must precede every app/bare import)`)
      }
    }
    expect(violations).toEqual([])
  })
})
