import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Ratchet guard for the shadcn-vue migration (see .omo/plans/shadcn-vue-component-library-migration.md).
 *
 * Test files that assert exact Tailwind classes (via `.classes(`, `.classList`,
 * `toHaveClass`, or full-DOM `.html()`/snapshot assertions) break on a correct
 * component rewrite, so the backlog is frozen in `classAssertionBaseline.json`
 * and can only shrink, never grow:
 *
 * - a file NOT in the baseline that asserts classes fails the suite (new coupling blocked);
 * - a baselined file that no longer asserts classes fails until its entry is removed
 *   (stale entries keep the list honest, same ratchet semantics as the backend's
 *   `test_service_layer_guard.py` / `test_item_factory_guard.py`).
 *
 * Class assertions are converted or deleted, never re-pointed at new class names.
 * The guard's own file is excluded from the scan.
 */

// Vitest runs with root = frontend/ (see vitest.config.ts), so process.cwd() is stable.
const UNIT_TESTS_DIR = join(process.cwd(), 'tests/unit')
const BASELINE_FILE = join(process.cwd(), 'tests/unit/architecture/classAssertionBaseline.json')
const GUARD_FILE = 'architecture/classAssertionGuard.test.ts'

const CLASS_ASSERTION_PATTERNS: ReadonlyArray<{ name: string; regex: RegExp }> = [
  { name: '.classes(', regex: /\.classes\(/ },
  { name: '.classList', regex: /\.classList/ },
  { name: 'toHaveClass', regex: /toHaveClass/ },
  { name: 'full-DOM .html() assertion', regex: /\.html\(\)|toMatchSnapshot/ },
]

interface Baseline {
  count: number
  files: string[]
}

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

function matchPatterns(source: string): string[] {
  return CLASS_ASSERTION_PATTERNS.filter(({ regex }) => regex.test(source)).map(({ name }) => name)
}

function findOffendingFiles(): Map<string, string[]> {
  const offenders = new Map<string, string[]>()
  for (const file of walkTestFiles(UNIT_TESTS_DIR)) {
    const rel = relative(UNIT_TESTS_DIR, file).split('\\').join('/')
    if (rel === GUARD_FILE) continue
    const matched = matchPatterns(readFileSync(file, 'utf8'))
    if (matched.length > 0) offenders.set(rel, matched)
  }
  return offenders
}

function loadBaseline(): Baseline {
  return JSON.parse(readFileSync(BASELINE_FILE, 'utf8')) as Baseline
}

describe('class-assertion ratchet guard', () => {
  it('freezes the class-assertion backlog: it can only shrink, never grow', () => {
    const found = findOffendingFiles()
    const baseline = loadBaseline()

    const newOffenders = [...found.keys()].filter((file) => !baseline.files.includes(file))
    const staleEntries = baseline.files.filter((file) => !found.has(file))

    const messages: string[] = []
    for (const file of newOffenders) {
      messages.push(
        `${file} asserts exact classes (${found.get(file)?.join(', ')}); convert to behaviour/aria/emits assertions or the ui-catalog visual net`
      )
    }
    for (const file of staleEntries) {
      messages.push(`baseline entry ${file} no longer offends; remove it from classAssertionBaseline.json`)
    }

    expect(messages).toEqual([])
  })

  it('keeps the recorded baseline count in sync with the file list', () => {
    const baseline = loadBaseline()
    expect(baseline.count).toBe(baseline.files.length)
  })

  it('detects every class-assertion pattern', () => {
    expect(matchPatterns("expect(wrapper.classes()).toContain('mt-4')")).toEqual(['.classes('])
    expect(matchPatterns("expect(el.classList).toContain('bg-x')")).toEqual(['.classList'])
    expect(matchPatterns('expect(wrapper).toHaveClass("text-red-400")')).toEqual(['toHaveClass'])
    expect(matchPatterns("expect(wrapper.html()).toContain('mt-4')")).toEqual(['full-DOM .html() assertion'])
    expect(matchPatterns('expect(wrapper.html()).toMatchSnapshot()')).toEqual(['full-DOM .html() assertion'])
    expect(matchPatterns("expect(wrapper.text()).toContain('Hello')")).toEqual([])
  })
})
