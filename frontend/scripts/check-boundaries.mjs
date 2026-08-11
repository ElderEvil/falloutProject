import { readFileSync, readdirSync } from 'node:fs'
import { join, relative } from 'node:path'

const root = new URL('../src/core/', import.meta.url)
const allowlistUrl = new URL('./boundary-allowlist.json', import.meta.url)
const allowlist = new Set(JSON.parse(readFileSync(allowlistUrl, 'utf8')))
// Boundary checks are release gates. `--warn` remains available for local
// exploration, but CI intentionally uses the default hard-fail mode.
const strict = !process.argv.includes('--warn')

function collectFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return collectFiles(path)
    return /\.(ts|vue)$/.test(entry.name) ? [path] : []
  })
}

const rootPath = root.pathname
const violations = collectFiles(rootPath).flatMap((file) => {
  const relativePath = relative(process.cwd(), file)
  if (allowlist.has(relativePath)) return []
  return /from\s*['"]@\/modules\//.test(readFileSync(file, 'utf8')) ? [relativePath] : []
})

if (violations.length === 0) {
  console.log('Module boundary check: no core → module imports found.')
} else {
  const mode = strict ? 'error' : 'warning'
  console[mode === 'error' ? 'error' : 'warn'](
    `Module boundary check (${mode}):\n${violations.map((file) => `- ${file}`).join('\n')}`
  )
}

if (strict && violations.length > 0) process.exitCode = 1
