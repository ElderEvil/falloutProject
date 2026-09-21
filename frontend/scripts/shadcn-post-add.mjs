#!/usr/bin/env node
// Inserts `<!-- @vue-ignore -->` before every component element that carries a `data-slot` attribute.
//
// Why this exists: shadcn-vue's registry templates pass `data-slot` to Reka UI components whose props
// type does not declare it. This repo keeps `strictTemplates: true`, so that is a hard TS2353 error on
// every generated component. `@vue-ignore` suppresses the check for that element only, and `data-slot`
// still reaches the DOM as a fallthrough attribute.
//
// Run after every `shadcn-vue add`. Idempotent — re-running changes nothing.

import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const UI_DIR = fileURLToPath(new URL('../src/core/components/ui', import.meta.url))
const IGNORE = '<!-- @vue-ignore -->'
const COMPONENT_TAG = /^(\s*)<([A-Z][\w.]*)\b/

const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) return walk(full)
    return full.endsWith('.vue') ? [full] : []
  })

const readTag = (lines, start) => {
  let text = ''
  let index = start
  while (index < lines.length) {
    text += `${lines[index]}\n`
    if (lines[index].includes('>')) break
    index += 1
  }
  return text
}

const annotate = (source) => {
  const lines = source.split('\n')
  const out = []
  let changed = 0
  for (let i = 0; i < lines.length; i += 1) {
    const match = COMPONENT_TAG.exec(lines[i])
    if (match && /data-slot\s*=/.test(readTag(lines, i))) {
      const previous = out.length > 0 ? out.at(-1).trim() : ''
      if (previous !== IGNORE) {
        out.push(`${match[1]}${IGNORE}`)
        changed += 1
      }
    }
    out.push(lines[i])
  }
  return { source: out.join('\n'), changed }
}

let total = 0
for (const file of walk(UI_DIR)) {
  const { source, changed } = annotate(readFileSync(file, 'utf8'))
  if (changed > 0) {
    writeFileSync(file, source)
    console.log(`  ${changed}  ${relative(process.cwd(), file)}`)
    total += changed
  }
}
console.log(total > 0 ? `shadcn-post-add: annotated ${total} element(s)` : 'shadcn-post-add: nothing to do')
