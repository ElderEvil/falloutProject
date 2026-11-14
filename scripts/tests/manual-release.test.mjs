import assert from 'node:assert/strict'
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { test } from 'node:test'

const workflow = readFileSync(new URL('../../.github/workflows/release.yml', import.meta.url), 'utf8')
const step = workflow.split('      - name: Run semantic-release\n')[1].split('\n      - name:')[0]
const shell = step.split('        run: |\n')[1].split('\n').map(line => line.slice(10)).join('\n')

for (const selection of ['', 'auto', 'patch', 'minor', 'major']) {
  const automatic = selection === '' || selection === 'auto'
  test(`workflow passes ${automatic ? 'automatic' : selection} analysis to semantic-release`, () => {
    const directory = mkdtempSync(join(tmpdir(), 'release-test-'))
    try {
      writeFileSync(join(directory, 'npx'), '#!/bin/sh\nprintf "%s\\n" "$@"\n', { mode: 0o755 })
      const result = spawnSync('bash', ['-e', '-c', shell], {
        encoding: 'utf8', env: { ...process.env, PATH: `${directory}:${process.env.PATH}`, RELEASE_AS: selection },
      })
      assert.equal(result.status, 0, result.stderr)
      assert.deepEqual(result.stdout.trim().split('\n'), [
        '--no', '--', 'semantic-release',
        ...(automatic ? [] : ['--analyze-commits', './scripts/manual-release.cjs']),
      ])
    } finally {
      rmSync(directory, { recursive: true })
    }
  })
}

const { analyzeCommits } = await import('../manual-release.cjs')
for (const type of ['patch', 'minor', 'major']) {
  test(`manual analyzer selects ${type} for chore-only history`, () => {
    assert.equal(analyzeCommits({}, { env: { RELEASE_AS: type }, commits: [{ message: 'chore: baseline' }] }), type)
  })
}
for (const type of [undefined, '', 'auto', 'invalid']) {
  test(`manual analyzer rejects ${String(type)}`, () => {
    assert.throws(() => analyzeCommits({}, { env: { RELEASE_AS: type } }), /Manual release requires/)
  })
}
