import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'

const DIST = 'dist'
// Initial payload = the render-blocking critical path (preloaded JS + CSS).
// Unit and E2E tests stay green while this regresses, so it is gated here.
const BUDGET_KB = 200

const html = fs.readFileSync(path.join(DIST, 'index.html'), 'utf8')
const refs = [
  ...new Set(
    [...html.matchAll(/(?:modulepreload[^>]*href="|src="|href=")([^"]+\.(?:js|css))"/g)].map((m) => m[1]),
  ),
]

const missing = refs.filter((r) => !fs.existsSync(path.join(DIST, r.replace(/^\//, ''))))
if (missing.length > 0) {
  console.error(`bundle budget: ${missing.length} referenced asset(s) missing from ${DIST}/:`)
  missing.forEach((m) => console.error(`  ${m}`))
  process.exit(1)
}

const rows = refs.map((ref) => {
  const file = path.join(DIST, ref.replace(/^\//, ''))
  return [ref.split('/').pop(), zlib.gzipSync(fs.readFileSync(file)).length / 1024]
})
const totalKb = rows.reduce((sum, [, kb]) => sum + kb, 0)

console.log(`initial payload: ${totalKb.toFixed(1)} kB gzip (budget ${BUDGET_KB} kB)`)
rows
  .sort((a, b) => b[1] - a[1])
  .forEach(([name, kb]) => console.log(`  ${String(name).padEnd(38)} ${kb.toFixed(1)} kB`))

if (totalKb > BUDGET_KB) {
  console.error(`\nFAIL: ${totalKb.toFixed(1)} kB exceeds the ${BUDGET_KB} kB gzip budget.`)
  console.error('This is the FCP/LCP critical path. Move the new code behind a dynamic import')
  console.error('rather than raising the budget; do not reintroduce a manualChunks map in vite.config.ts.')
  process.exit(1)
}

console.log('\nOK: within budget')
