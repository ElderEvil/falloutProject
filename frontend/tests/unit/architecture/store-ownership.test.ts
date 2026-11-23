import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vite-plus/test'

/**
 * Cross-store-write ratchet (Phase 0.3).
 *
 * Components and sibling stores must not mutate another module's store refs
 * directly — they go through the owning store's actions so its invariants hold.
 * This guard is deliberately crude and textual: it finds files that import a
 * store composable from another module (`@/modules/<module>/stores/...`) and
 * then assign a property on that store, call push/splice/sort on it, or assign
 * `.value` on a store ref.
 *
 * The measured backlog is frozen in CROSS_STORE_WRITE_BASELINE. The map may
 * only shrink: a new pair, a grown count, or a stale entry all fail, and the
 * fix is to remove the write (or lower the recorded count), never raise it.
 * The owning store's own file and same-module imports are ignored.
 */

export interface SourceFile {
  path: string
  content: string
}

const STORE_ALIAS_RE = /^@\/modules\/([^/]+)\/stores\//
const OWN_MODULE_RE = /(?:^|\/)modules\/([^/]+)\//

const STORE_IMPORT_RE = /(?:^|\n)\s*import\s+(type\s+)?([\s\S]*?)\s*from\s*['"]([^'"]+)['"]/g
const DYNAMIC_STORE_IMPORT_RE =
  /(?:const|let|var)\s*\{([^}]*)\}\s*=\s*await\s+import\(\s*['"]([^'"]+)['"]\s*\)/g

interface ImportedStore {
  /** Local binding as written in the file (e.g. `useRoomStore`). */
  binding: string
  /** Store file it resolves to, when the module alias is a store path. */
  storePath: string | null
}

function escapeRe(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function parseImportBindings(clause: string): string[] {
  const trimmed = clause.trim()
  if (!trimmed) return []
  if (trimmed.startsWith('*')) return []
  const bindings: string[] = []
  const named = /\{([\s\S]*)\}/.exec(trimmed)
  if (named) {
    for (const rawPart of named[1].split(',')) {
      const part = rawPart.trim()
      if (!part || part.startsWith('type ')) continue
      const [imported, local] = part.split(/\s+as\s+/)
      bindings.push((local ?? imported).trim())
    }
  }
  const defaultPart = trimmed.replace(/\{[\s\S]*\}/, '').replace(/,/g, '').trim()
  if (defaultPart) bindings.push(defaultPart)
  return bindings
}

function readStoreImports(content: string): ImportedStore[] {
  const imports: ImportedStore[] = []
  STORE_IMPORT_RE.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = STORE_IMPORT_RE.exec(content)) !== null) {
    if (match[1]) continue // `import type` binds no runtime store
    const specifier = match[3]
    if (!STORE_ALIAS_RE.test(specifier)) continue
    const storePath = `src${specifier.slice(1)}` // @/ -> src/
    for (const binding of parseImportBindings(match[2])) {
      imports.push({ binding, storePath })
    }
  }

  // `const { useDwellerStore } = await import('@/modules/dwellers/stores/dweller')`
  DYNAMIC_STORE_IMPORT_RE.lastIndex = 0
  while ((match = DYNAMIC_STORE_IMPORT_RE.exec(content)) !== null) {
    const specifier = match[2]
    if (!STORE_ALIAS_RE.test(specifier)) continue
    const storePath = `src${specifier.slice(1)}`
    for (const binding of parseImportBindings(`{${match[1]}}`)) {
      imports.push({ binding, storePath })
    }
  }
  return imports
}

/** Local names that hold (part of) an imported store. */
function collectAliases(content: string, binding: string): string[] {
  const name = escapeRe(binding)
  const aliases = new Set<string>([binding])
  const whole = new RegExp(`\\b(?:const|let|var)\\s+([A-Za-z_$][\\w$]*)\\s*=\\s*${name}\\s*\\(`, 'g')
  const destructured = new RegExp(
    `\\b(?:const|let|var)\\s*\\{([^}]*)\\}\\s*=\\s*${name}\\s*\\(`,
    'g'
  )
  let match: RegExpExecArray | null
  while ((match = whole.exec(content)) !== null) aliases.add(match[1])
  while ((match = destructured.exec(content)) !== null) {
    for (const rawPart of match[1].split(',')) {
      const part = rawPart.trim()
      if (!part) continue
      const [key, local] = part.split(/\s*:\s*/)
      const target = (local ?? key).trim()
      if (target && /^[A-Za-z_$][\w$]*$/.test(target)) aliases.add(target)
    }
  }
  // Refs obtained via storeToRefs: `const { a } = storeToRefs(roomStore)`.
  // Follow aliases of aliases (a store slice can itself be passed to storeToRefs).
  const queue = [...aliases]
  while (queue.length > 0) {
    const current = queue.pop() as string
    const refs = new RegExp(
      `\\b(?:const|let|var)\\s*\\{([^}]*)\\}\\s*=\\s*storeToRefs\\(\\s*${escapeRe(current)}\\s*\\)`,
      'g'
    )
    let refMatch: RegExpExecArray | null
    while ((refMatch = refs.exec(content)) !== null) {
      for (const rawPart of refMatch[1].split(',')) {
        const part = rawPart.trim()
        if (!part) continue
        const [key, local] = part.split(/\s*:\s*/)
        const target = (local ?? key).trim()
        if (target && /^[A-Za-z_$][\w$]*$/.test(target) && !aliases.has(target)) {
          aliases.add(target)
          queue.push(target)
        }
      }
    }
  }
  return [...aliases]
}

function countWrites(content: string, name: string): number {
  const identifier = escapeRe(name)
  const chain = `(?:\\s*\\.\\s*[A-Za-z_$][\\w$]*|\\s*\\[[^\\]]*\\])+`
  const patterns: RegExp[] = [
    // Assigning a property on the store or one of its refs: `store.x = ...`, `ref.value = ...`
    new RegExp(`(?<![\\w$.])${identifier}(?![\\w$])${chain}\\s*(?:=|\\+=|-=)(?!=|>)`, 'g'),
    // In-place mutation of an array owned by / exposed from the store.
    new RegExp(`(?<![\\w$.])${identifier}(?![\\w$])${chain}\\s*\\.\\s*(?:push|splice|sort)\\s*\\(`, 'g'),
  ]
  let total = 0
  for (const pattern of patterns) {
    total += content.match(pattern)?.length ?? 0
  }
  return total
}

export function scanCrossStoreWrites(files: readonly SourceFile[]): Map<string, number> {
  const found = new Map<string, number>()
  for (const file of files) {
    const normalizedPath = file.path.split('\\').join('/')
    if (!/\.(ts|vue)$/.test(normalizedPath)) continue
    const ownModule = OWN_MODULE_RE.exec(normalizedPath)?.[1] ?? null

    const seen = new Set<string>()
    for (const imported of readStoreImports(file.content)) {
      const importKey = `${imported.storePath ?? '<relative>'}|${imported.binding}`
      if (seen.has(importKey)) continue
      seen.add(importKey)
      const targetModule = imported.storePath ? /^src\/modules\/([^/]+)\//.exec(imported.storePath)?.[1] : null
      // Same-module imports and relative store files are the module's own business.
      if (targetModule !== null && targetModule === ownModule) continue
      if (imported.storePath !== null && imported.storePath === normalizedPath) continue

      let writes = 0
      for (const alias of collectAliases(file.content, imported.binding)) {
        writes += countWrites(file.content, alias)
      }
      if (writes > 0) {
        const key = `${normalizedPath} -> ${imported.binding}`
        found.set(key, (found.get(key) ?? 0) + writes)
      }
    }
  }
  return found
}

export const CROSS_STORE_WRITE_BASELINE = new Map<string, number>([
  ['src/modules/chat/composables/useChatActions.ts -> useDwellerStore', 1],
  ['src/modules/progression/stores/training.ts -> useVaultStore', 1],
  ['src/modules/rooms/components/BarbershopPanel.vue -> useDwellerStore', 2],
  ['src/modules/rooms/stores/room.ts -> useDwellerStore', 4],
])

const FRONTEND_ROOT = process.cwd()
const SRC_DIR = join(FRONTEND_ROOT, 'src')

function walkSourceFiles(dir: string): SourceFile[] {
  const files: SourceFile[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      files.push(...walkSourceFiles(full))
    } else if (entry.endsWith('.ts') || entry.endsWith('.vue')) {
      files.push({ path: relative(FRONTEND_ROOT, full).split('\\').join('/'), content: readFileSync(full, 'utf8') })
    }
  }
  return files
}

function sortedEntries(map: Map<string, number>): Array<[string, number]> {
  return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
}

describe('cross-store-write ratchet', () => {
  it('matches the frozen baseline; the baseline may only shrink', () => {
    const found = scanCrossStoreWrites(walkSourceFiles(SRC_DIR))
    const messages: string[] = []

    for (const [key, count] of sortedEntries(found)) {
      const baselined = CROSS_STORE_WRITE_BASELINE.get(key)
      if (baselined === undefined) {
        messages.push(
          `NEW cross-store write: ${key} (${count} site${count === 1 ? '' : 's'}) — route it through the owning store action; the baseline only shrinks.`
        )
      } else if (count > baselined) {
        messages.push(
          `GROWN cross-store write: ${key} went from ${baselined} to ${count} site${count === 1 ? '' : 's'} — route the extra write through the owning store action; the baseline only shrinks.`
        )
      } else if (count < baselined) {
        messages.push(
          `STALE baseline count: ${key} recorded ${baselined} but only ${count} remain${count === 1 ? 's' : ''} — lower the count (and shrink the ratchet).`
        )
      }
    }
    for (const [key, baselined] of sortedEntries(CROSS_STORE_WRITE_BASELINE)) {
      if (!found.has(key)) {
        messages.push(
          `STALE baseline entry: ${key} is no longer written here (was ${baselined}) — remove it from CROSS_STORE_WRITE_BASELINE and shrink the ratchet.`
        )
      }
    }

    expect(messages).toEqual([])
    expect(found.size).toBe(CROSS_STORE_WRITE_BASELINE.size)
  })
})

describe('scanCrossStoreWrites fixtures', () => {
  it('flags a new cross-module write as a new key', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/chat/components/QuickBuild.vue',
        content: `
          <script setup lang="ts">
          import { useRoomStore } from '@/modules/rooms/stores/room'
          const roomStore = useRoomStore()
          roomStore.selectedRoom = null
          </script>
        `,
      },
    ])

    expect([...found]).toEqual([['src/modules/chat/components/QuickBuild.vue -> useRoomStore', 1]])
  })

  it('counts a second write between already-listed files as growth', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/rooms/stores/room.ts',
        content: `
          import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
          const { filter } = useDwellerStore()
          filter.dwellers = filter.dwellers.map(repoint)
          filter.allDwellers = filter.allDwellers.map(repoint)
        `,
      },
    ])

    expect(found.get('src/modules/rooms/stores/room.ts -> useDwellerStore')).toBe(2)
  })

  it('does not flag the owning store mutating its own state', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/dwellers/stores/dwellerFilter.ts',
        content: `
          import { defineStore } from 'pinia'
          import { ref } from 'vue'
          export const useDwellerFilterStore = defineStore('dwellerFilter', () => {
            const dwellers = ref([])
            dwellers.value = []
            dwellers.value.push({ id: 1 })
            return { dwellers }
          })
        `,
      },
    ])

    expect([...found]).toEqual([])
  })

  it('does not flag same-module imports', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/rooms/stores/arena.ts',
        content: `
          import { useRoomStore } from '@/modules/rooms/stores/room'
          const roomStore = useRoomStore()
          roomStore.selectedRoom = null
        `,
      },
    ])

    expect([...found]).toEqual([])
  })

  it('does not flag read-only store usage', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/progression/components/QuestCard.vue',
        content: `
          <script setup lang="ts">
          import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
          const dwellerFilterStore = useDwellerFilterStore()
          const qualified = dwellerFilterStore.dwellers.filter((d) => d.level >= 3)
          const same = dwellerFilterStore.dwellers === qualified
          </script>
        `,
      },
    ])

    expect([...found]).toEqual([])
  })

  it('flags .value assignment on a ref from storeToRefs', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/profile/components/SyncBadge.vue',
        content: `
          <script setup lang="ts">
          import { storeToRefs } from 'pinia'
          import { useVaultStore } from '@/modules/vault/stores/vault'
          const vaultStore = useVaultStore()
          const { vault, isLoading } = storeToRefs(vaultStore)
          vault.value = null
          isLoading.value = true
          </script>
        `,
      },
    ])

    expect(found.get('src/modules/profile/components/SyncBadge.vue -> useVaultStore')).toBe(2)
  })
})
