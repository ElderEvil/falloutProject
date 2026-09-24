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
// Only the prop surface matters: an interface/type used as the defineProps
// argument. Object literals elsewhere (`{ 'data-slot': 'switch' }`) are not props.
const PROP_TYPE = /(?:interface|type)\s+(\w+)(?:\s*<[^>]*>)?\s*(?:=\s*)?\{([\s\S]*?)\}/g
const DEFINE_PROPS = /defineProps<\s*(\w+)\s*>/g

function propTypeBodies(source: string): string {
  const named = new Map<string, string>()
  for (const match of source.matchAll(PROP_TYPE)) named.set(match[1], match[2])

  const bodies: string[] = []
  for (const match of source.matchAll(DEFINE_PROPS)) {
    const body = named.get(match[1])
    if (body) bodies.push(body)
  }
  return bodies.join('\n')
}

export function hyphenatedOnlyDeclarations(source: string): string[] {
  const declared = new Set<string>()
  for (const match of propTypeBodies(source).matchAll(HYPHENATED_KEY)) {
    const key = match[1]
    if (KEBAB_PREFIX.test(key)) declared.add(key)
  }
  const offenders: string[] = []
  for (const key of declared) {
    const camel = key.replace(/-([a-z])/g, (_, char: string) => char.toUpperCase())
    // Accept the kebab key only when the camelCase sibling is also declared.
    if (!new RegExp(String.raw`\b${camel}\b\s*\??:`).test(source)) offenders.push(key)
  }
  return offenders.sort()
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
})
