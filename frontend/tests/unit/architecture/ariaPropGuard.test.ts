import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Guard for the `aria-*` / `data-*` prop convention in docs/frontend/ACCESSIBILITY.md.
 *
 * A quoted-hyphenated key as the *only* declaration for an aria prop
 * (`'aria-label'?: string`) is not reliably populated by Vue and silently
 * renders nothing; `HealthRadiationBar` shipped without an accessible name for
 * a period because of `const { 'aria-label': ariaLabel } = defineProps(...)`.
 *
 * The rule: an aria/data prop must be declared in camelCase, or declared in
 * *both* spellings when a Reka child reads raw `$attrs` and the kebab form is
 * needed for `strictTemplates`. A hyphenated-only declaration fails this guard.
 *
 * This guard's own file is excluded from the scan.
 */

const SRC_DIR = join(process.cwd(), 'src')

// `'aria-foo'?: type` / `'data-foo'?: type` written as a quoted property key.
const HYPHENATED_KEY = /['"]([a-z]+(?:-[a-z]+)+)['"]\s*\??:/g
const KEBAB_PREFIX = /^(?:aria|data)-/

/** The balanced `{...}` region starting at `open`, honouring nested braces. */
function balancedBraces(source: string, open: number): string {
  let depth = 0
  for (let i = open; i < source.length; i++) {
    if (source[i] === '{') depth++
    else if (source[i] === '}') {
      depth--
      if (depth === 0) return source.slice(open + 1, i)
    }
  }
  return source.slice(open + 1)
}

/** A named `interface Props {…}` / `type Props = {…}` body, brace-balanced. */
function namedTypeBody(source: string, name: string): string | undefined {
  const re = new RegExp(String.raw`(?:interface|type)\s+${name}\b[^{]*\{`)
  const match = re.exec(source)
  return match ? balancedBraces(source, match.index + match[0].length - 1) : undefined
}

/**
 * The prop surface only: every `defineProps<…>()` argument, whether it is an
 * inline type literal or a named interface/type. Object literals elsewhere
 * (`{ 'data-slot': 'switch' }`) are not props.
 */
export function propTypeBodies(source: string): string[] {
  const bodies: string[] = []
  const re = /defineProps\s*<\s*/g
  for (const match of source.matchAll(re)) {
    const start = match.index + match[0].length
    if (source[start] === '{') {
      bodies.push(balancedBraces(source, start))
      continue
    }
    const name = /^\w+/.exec(source.slice(start))?.[0]
    const body = name ? namedTypeBody(source, name) : undefined
    if (body) bodies.push(body)
  }
  return bodies
}

export function hyphenatedOnlyDeclarations(source: string): string[] {
  const offenders = new Set<string>()
  for (const body of propTypeBodies(source)) {
    const kebab: string[] = []
    for (const match of body.matchAll(HYPHENATED_KEY)) {
      if (KEBAB_PREFIX.test(match[1])) kebab.push(match[1])
    }
    for (const key of kebab) {
      const camel = key.replace(/-([a-z])/g, (_, char: string) => char.toUpperCase())
      // The camelCase sibling must live in the SAME prop type, not anywhere in the file.
      if (!new RegExp(String.raw`\b${camel}\b\s*\??:`).test(body)) offenders.add(key)
    }
  }
  return [...offenders].sort()
}

function walkVueFiles(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) files.push(...walkVueFiles(full))
    else if (entry.endsWith('.vue')) files.push(full)
  }
  return files
}

describe('aria prop convention guard', () => {
  it('rejects a hyphenated aria/data prop declared without its camelCase sibling', () => {
    const offenders = new Map<string, string[]>()
    for (const file of walkVueFiles(SRC_DIR)) {
      const rel = relative(SRC_DIR, file).split('\\').join('/')
      const found = hyphenatedOnlyDeclarations(readFileSync(file, 'utf8'))
      if (found.length > 0) offenders.set(rel, found)
    }
    const messages = [...offenders.entries()].map(
      ([file, keys]) =>
        `${file} declares ${keys.join(', ')} without a camelCase prop; declare e.g. ariaLabel and bind it (see docs/frontend/ACCESSIBILITY.md)`
    )
    expect(messages).toEqual([])
  })

  it('detects the offending and the accepted forms', () => {
    const kebabOnly = `
      interface Props { 'aria-label'?: string }
      const props = defineProps<Props>()
    `
    const bothSpellings = `
      interface Props { 'aria-label'?: string; ariaLabel?: string }
      const props = defineProps<Props>()
    `
    const camelOnly = `
      interface Props { ariaLabel?: string }
      const props = defineProps<Props>()
    `
    const dataKebab = `
      interface Props { 'data-state'?: string }
      const props = defineProps<Props>()
    `
    const objectLiteral = `
      const rootAttrs = { 'data-slot': 'switch' } as const
      const thumbAttrs = { 'data-slot': 'switch-thumb' } as const
    `

    expect(hyphenatedOnlyDeclarations(kebabOnly)).toEqual(['aria-label'])
    expect(hyphenatedOnlyDeclarations(bothSpellings)).toEqual([])
    expect(hyphenatedOnlyDeclarations(camelOnly)).toEqual([])
    expect(hyphenatedOnlyDeclarations(dataKebab)).toEqual(['data-state'])
    expect(hyphenatedOnlyDeclarations(objectLiteral)).toEqual([])
  })

  it('scans inline defineProps type literals, not only named types', () => {
    const inlineKebabOnly = `const props = defineProps<{ 'aria-label'?: string }>()`
    const inlineBoth = `const props = defineProps<{ 'aria-label'?: string; ariaLabel?: string }>()`

    expect(hyphenatedOnlyDeclarations(inlineKebabOnly)).toEqual(['aria-label'])
    expect(hyphenatedOnlyDeclarations(inlineBoth)).toEqual([])
  })

  it('requires the camelCase sibling in the same prop type, not elsewhere in the file', () => {
    const unrelatedSibling = `
      interface Props { 'aria-label'?: string }
      interface Other { ariaLabel?: string }
      const props = defineProps<Props>()
    `
    const nestedFields = `
      interface Props {
        thing?: { a?: string }
        'aria-label'?: string
      }
      const props = defineProps<Props>()
    `

    expect(hyphenatedOnlyDeclarations(unrelatedSibling)).toEqual(['aria-label'])
    expect(hyphenatedOnlyDeclarations(nestedFields)).toEqual(['aria-label'])
  })
})
