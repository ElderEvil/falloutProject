import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

// Color literals are release gates. `--warn` remains available for local
// exploration, but CI intentionally uses the default hard-fail mode.
const strict = !process.argv.includes('--warn')
const update = process.argv.includes('--update')

// Files that legitimately define the palette itself.
const DEFINITION_FILES = new Set([
  'src/assets/tailwind.css',
  'src/core/composables/useTheme.ts',
])

const SCAN_EXT = /\.(ts|vue|css)$/
const COLOR_FN = String.raw`(?:rgb|rgba|hsl|hsla)\((?:[^()]|\([^()]*\))*\)`
const HEX = String.raw`#[0-9a-fA-F]{3,8}\b`
// A color used only as a var() fallback (e.g. `var(--color-theme-primary, #00ff00)`)
// is theme-aware intent, not a hardcoded value.
const VAR_FALLBACK = new RegExp(
  String.raw`var\(\s*--[\w-]+\s*,\s*(?:${HEX}|${COLOR_FN})\s*\)`,
  'g'
)
const HEX_RE = new RegExp(HEX, 'g')
const COLOR_FN_RE = new RegExp(COLOR_FN, 'g')
const NEUTRAL_HEX = /^#(?:000|0000|000000|fff|ffff|ffffff)$/i

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

function isNeutralColorFn(text) {
  const nums = (text.slice(text.indexOf('(') + 1).match(/\d+(?:\.\d+)?/g) || []).map(Number)
  if (nums.length < 3) return false
  const [r, g, b] = nums
  return (r === 0 && g === 0 && b === 0) || (r === 255 && g === 255 && b === 255)
}

/**
 * Literal color values that are neither token-derived nor neutral black/white.
 * `rgb(from var(--color-theme-primary) r g b / 0.2)` and var() fallbacks pass.
 */
export function findHardcodedColors(source) {
  const stripped = source.replace(VAR_FALLBACK, 'var(--token)')
  const found = []

  for (const match of stripped.matchAll(HEX_RE)) {
    if (!NEUTRAL_HEX.test(match[0])) found.push(match[0])
  }
  for (const match of stripped.matchAll(COLOR_FN_RE)) {
    if (match[0].includes('var(')) continue
    if (isNeutralColorFn(match[0])) continue
    found.push(match[0])
  }
  return found
}

/** Per-file hardcoded-color counts, keyed by path relative to `cwd`. */
export function collectViolations(files, cwd) {
  const counts = {}
  for (const file of files) {
    const relativePath = relative(cwd, file)
    if (DEFINITION_FILES.has(relativePath)) continue
    const found = findHardcodedColors(readFileSync(file, 'utf8'))
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
  const baselineUrl = new URL('./hardcoded-color-baseline.json', import.meta.url)

  const actual = collectViolations(collectFiles(srcPath), cwd)

  if (update) {
    writeFileSync(baselineUrl, `${JSON.stringify(actual, null, 2)}\n`)
    console.log(
      `Hardcoded color baseline updated: ${total(actual)} literals across ${Object.keys(actual).length} files.`
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
      `Hardcoded color check: OK (${total(actual)} grandfathered literals across ${Object.keys(baseline).length} files; baseline must shrink, never grow).`
    )
  } else {
    const lines = []
    if (added.length) {
      lines.push('New hardcoded colors — use a design token (var(--color-*) or a Tailwind token class):')
      lines.push(...added.map((v) => `  + ${v.file} (${v.count})`))
    }
    if (grown.length) {
      lines.push('More hardcoded colors than the baseline allows:')
      lines.push(...grown.map((v) => `  ↑ ${v.file} (${v.allowed} → ${v.count})`))
    }
    if (stale.length) {
      lines.push(
        'Baseline is stale (fewer violations than recorded) — run `node scripts/check-hardcoded-colors.mjs --update` to ratchet it down:'
      )
      lines.push(...stale.map((v) => `  ↓ ${v.file} (${v.allowed} → ${v.count})`))
    }
    const mode = strict ? 'error' : 'warning'
    console[mode === 'error' ? 'error' : 'warn'](
      `Hardcoded color check (${mode}):\n${lines.join('\n')}`
    )
  }

  if (strict && problems > 0) process.exitCode = 1
}
