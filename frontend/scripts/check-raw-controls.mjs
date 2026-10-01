import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

// Raw native controls are release gates. `--warn` remains available for local
// exploration, but CI intentionally uses the default hard-fail mode.
const strict = !process.argv.includes('--warn')
const update = process.argv.includes('--update')

// Only modules/**/*.vue are in scope: the dev-only catalog is a fixture.
// See docs/frontend/RAW_NATIVE_CONTROLS.md for the frozen accounting.
const SCOPE = join('src', 'modules')

// Primitives vendored in src/core/components/ui/. A raw control is only a
// violation where one of these exists; `textarea` and `table` have no primitive
// and stay exempt until they are vendored (see the doc's "Driving it to zero").
const PRIMITIVE_BACKED = new Set(['button', 'input', 'select'])

const SCAN_EXT = /\.vue$/
const TAG = /<(button|input|select|textarea|table)\b/gi

export function collectFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist') return []
      return collectFiles(path)
    }
    return SCAN_EXT.test(entry.name) ? [path] : []
  })
}

/** Raw native controls that have a vendored primitive, so they are migratable. */
export function findRawControls(source) {
  const template = source.match(/<template\b[^>]*>([\s\S]*)<\/template>/)
  if (!template) return []
  const markup = template[1].replace(/<!--[\s\S]*?-->/g, '')
  const found = []
  for (const match of markup.matchAll(TAG)) {
    const tag = match[1].toLowerCase()
    if (PRIMITIVE_BACKED.has(tag)) found.push(tag)
  }
  return found
}

/** Per-file raw-control counts, keyed by path relative to `cwd`. */
export function collectViolations(files, cwd) {
  const counts = {}
  for (const file of files) {
    const relativePath = relative(cwd, file).split(sep).join('/')
    if (!relativePath.startsWith(SCOPE.split(sep).join('/'))) continue
    const found = findRawControls(readFileSync(file, 'utf8'))
    if (found.length > 0) counts[relativePath] = found.length
  }
  return Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)))
}

const total = (counts) => Object.values(counts).reduce((sum, count) => sum + count, 0)

const isMainModule =
  import.meta.url.startsWith('file:') &&
  process.argv[1] &&
  fileURLToPath(import.meta.url) === process.argv[1]

if (isMainModule) {
  const cwd = fileURLToPath(new URL('..', import.meta.url))
  const srcPath = fileURLToPath(new URL('../src/', import.meta.url))
  const baselineUrl = new URL('./raw-control-baseline.json', import.meta.url)

  const actual = collectViolations(collectFiles(srcPath), cwd)

  if (update) {
    writeFileSync(baselineUrl, `${JSON.stringify(actual, null, 2)}\n`)
    console.log(
      `Raw control baseline updated: ${total(actual)} controls across ${Object.keys(actual).length} files.`
    )
    process.exit(0)
  }

  const baseline = JSON.parse(readFileSync(baselineUrl, 'utf8'))
  const added = []
  const grown = []
  const stale = []

  for (const [file, count] of Object.entries(actual)) {
    const allowed = baseline[file]
    if (allowed == null) added.push({ file, count })
    else if (count > allowed) grown.push({ file, allowed, count })
    else if (count < allowed) stale.push({ file, allowed, count })
  }
  for (const [file, allowed] of Object.entries(baseline)) {
    if (actual[file] == null) stale.push({ file, allowed, count: 0 })
  }

  const problems = added.length + grown.length + stale.length

  if (problems === 0) {
    console.log(
      `Raw control check: OK (${total(actual)} grandfathered controls across ${Object.keys(baseline).length} files; baseline must shrink, never grow).`
    )
  } else {
    const lines = []
    if (added.length) {
      lines.push(
        'New raw controls — use the shared primitive (Button, Input, Select) from @/core/components/ui:'
      )
      lines.push(...added.map((v) => `  + ${v.file} (${v.count})`))
    }
    if (grown.length) {
      lines.push('More raw controls than the baseline allows:')
      lines.push(...grown.map((v) => `  ↑ ${v.file} (${v.allowed} → ${v.count})`))
    }
    if (stale.length) {
      lines.push(
        'Baseline is stale (fewer controls than recorded) — run `node scripts/check-raw-controls.mjs --update` to ratchet it down:'
      )
      lines.push(...stale.map((v) => `  ↓ ${v.file} (${v.allowed} → ${v.count})`))
    }
    const mode = strict ? 'error' : 'warning'
    console[mode === 'error' ? 'error' : 'warn'](`Raw control check (${mode}):\n${lines.join('\n')}`)
  }

  if (strict && problems > 0) process.exitCode = 1
}
