import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Import-order guard for the shared test mocks (see tests/unit/helpers/mocks).
 *
 * The axios/router/iconify factories run when the mocked module is first
 * imported, so the helper module must already be evaluated: the helpers
 * import has to precede any import that can pull in a mocked module or the
 * component under test. Toast factory calls happen at module scope and are
 * order-independent, so only axios/router/iconify factory calls are checked.
 */

const UNIT_TESTS_DIR = join(process.cwd(), 'tests/unit')
const SELF = 'architecture/mockImportOrderGuard.test.ts'
const HELPER_IMPORT = /from\s+['"](?:\.\.?\/)+helpers\/mocks['"]/
const FACTORY_CALL = /create(?:Axios|Router|Iconify)Mock\s*\(/
const RISKY_IMPORT = /^import\s+(?:.*\s+from\s+)?['"]((?:@\/|\.\.?\/)(?!.*helpers\/mocks)[^'"]*)['"]/

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
      const lines = readFileSync(file, 'utf8').split('\n')
      if (!lines.some((line) => FACTORY_CALL.test(line))) continue
      const helperLine = lines.findIndex((line) => HELPER_IMPORT.test(line))
      const riskyLine = lines.findIndex((line) => RISKY_IMPORT.test(line))
      if (helperLine === -1 || riskyLine === -1 || helperLine > riskyLine) {
        violations.push(`${rel} (helper@${helperLine + 1}, first risky import@${riskyLine + 1})`)
      }
    }
    expect(violations).toEqual([])
  })
})
