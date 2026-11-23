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

/**
 * Local name introduced by one import specifier. Static named imports rename
 * with `as` (`{ useRoomStore as room }`); destructured dynamic imports rename
 * with `:` (`{ useRoomStore: getRoomStore }`). Both must yield the local name,
 * otherwise writes through the renamed alias are invisible to the scanner.
 */
function importLocalName(part: string): string {
  const [imported, ...asRest] = part.split(/\s+as\s+/)
  if (asRest.length > 0) return asRest.join(' as ').trim()
  const colon = imported.indexOf(':')
  if (colon !== -1) return imported.slice(colon + 1).trim()
  return imported.trim()
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
      const local = importLocalName(part)
      if (local) bindings.push(local)
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

interface AliasBinding {
  name: string
  /** Lexical span (character offsets) in which writes to this name are owned. */
  start: number
  end: number
}

/**
 * Innermost block enclosing `index`: the span between the nearest unbalanced
 * `{` before it and its matching `}`. Falls back to the whole file when the
 * declaration sits at module scope, which keeps module-level aliases visible
 * everywhere (and keeps the ratchet conservative).
 */
function enclosingScope(content: string, index: number): { start: number; end: number } {
  let depth = 0
  let open = -1
  for (let i = index - 1; i >= 0; i -= 1) {
    const ch = content[i]
    if (ch === '}') {
      depth += 1
    } else if (ch === '{') {
      if (depth === 0) {
        open = i
        break
      }
      depth -= 1
    }
  }
  if (open === -1) return { start: 0, end: content.length }
  depth = 0
  for (let i = open; i < content.length; i += 1) {
    const ch = content[i]
    if (ch === '{') {
      depth += 1
    } else if (ch === '}') {
      depth -= 1
      if (depth === 0) return { start: open, end: i + 1 }
    }
  }
  return { start: open, end: content.length }
}

function destructuredLocals(list: string): string[] {
  const names: string[] = []
  for (const rawPart of list.split(',')) {
    const part = rawPart.trim()
    if (!part) continue
    const [key, local] = part.split(/\s*:\s*/)
    const target = (local ?? key).trim()
    if (target && /^[A-Za-z_$][\w$]*$/.test(target)) names.push(target)
  }
  return names
}

/**
 * Local names that hold (part of) an imported store, each tied to the lexical
 * scope of its declaration. The same name declared in two functions therefore
 * yields two bindings, and a write only counts in the scope that declared it.
 */
function collectAliases(content: string, binding: string): AliasBinding[] {
  const aliases: AliasBinding[] = []
  const seen = new Set<string>()
  const add = (name: string, index: number): boolean => {
    if (!/^[A-Za-z_$][\w$]*$/.test(name)) return false
    const scope = enclosingScope(content, index)
    const key = `${name}@${scope.start}:${scope.end}`
    if (seen.has(key)) return false
    seen.add(key)
    aliases.push({ name, start: scope.start, end: scope.end })
    return true
  }

  add(binding, 0) // the import binding itself lives at module scope
  const queue: string[] = [binding]
  while (queue.length > 0) {
    const current = queue.pop() as string
    const name = escapeRe(current)
    const whole = new RegExp(
      `\\b(?:const|let|var)\\s+([A-Za-z_$][\\w$]*)\\s*=\\s*${name}\\s*\\(`,
      'g'
    )
    const destructured = new RegExp(
      `\\b(?:const|let|var)\\s*\\{([^}]*)\\}\\s*=\\s*${name}\\s*\\(`,
      'g'
    )
    const refs = new RegExp(
      `\\b(?:const|let|var)\\s*\\{([^}]*)\\}\\s*=\\s*storeToRefs\\(\\s*${name}\\s*\\)`,
      'g'
    )

    let match: RegExpExecArray | null
    while ((match = whole.exec(content)) !== null) {
      if (add(match[1], match.index)) queue.push(match[1])
    }
    while ((match = destructured.exec(content)) !== null) {
      for (const local of destructuredLocals(match[1])) {
        if (add(local, match.index)) queue.push(local)
      }
    }
    // Refs obtained via storeToRefs: `const { a } = storeToRefs(roomStore)`.
    while ((match = refs.exec(content)) !== null) {
      for (const local of destructuredLocals(match[1])) {
        if (add(local, match.index)) queue.push(local)
      }
    }
  }
  return aliases
}

/** Offsets of every write site through `name`, regardless of scope. */
function findWrites(content: string, name: string): number[] {
  const identifier = escapeRe(name)
  // Property assignments need at least one step of chain: `store.x = ...`.
  const chain = `(?:\\s*\\.\\s*[A-Za-z_$][\\w$]*|\\s*\\[[^\\]]*\\])+`
  // Array mutations may be bare (`dwellers.push(...)` after destructuring).
  const mutationChain = `(?:\\s*\\.\\s*[A-Za-z_$][\\w$]*|\\s*\\[[^\\]]*\\])*`
  const patterns: RegExp[] = [
    // Assigning a property on the store or one of its refs: `store.x = ...`, `ref.value = ...`
    new RegExp(`(?<![\\w$.])${identifier}(?![\\w$])${chain}\\s*(?:=|\\+=|-=)(?!=|>)`, 'g'),
    // In-place mutation of an array owned by / exposed from the store, or a
    // direct state patch: `store.$patch({ x: 1 })`. Like the array methods a
    // `$patch` call may hang off a bare alias (no intermediate property step).
    new RegExp(
      `(?<![\\w$.])${identifier}(?![\\w$])${mutationChain}\\s*\\.\\s*(?:push|splice|sort|pop|shift|unshift|\\$patch)\\s*\\(`,
      'g'
    ),
  ]
  const sites = new Set<number>()
  for (const pattern of patterns) {
    for (const match of content.matchAll(pattern)) {
      sites.add(match.index ?? 0)
    }
  }
  return [...sites]
}

/** Writes through a name that fall inside a scope which declared that name. */
function countWrites(content: string, bindings: readonly AliasBinding[]): number {
  const sites = new Set<number>()
  for (const site of findWrites(content, bindings[0].name)) {
    if (bindings.some((binding) => site >= binding.start && site < binding.end)) sites.add(site)
  }
  return sites.size
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

      // Group alias declarations by local name; a write counts once as long as
      // it sits inside any scope that declared that name.
      const byName = new Map<string, AliasBinding[]>()
      for (const alias of collectAliases(file.content, imported.binding)) {
        const list = byName.get(alias.name) ?? []
        list.push(alias)
        byName.set(alias.name, list)
      }
      let writes = 0
      for (const bindings of byName.values()) {
        writes += countWrites(file.content, bindings)
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

  it('flags a write through a renamed dynamic-import alias', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/chat/composables/useRoomSelection.ts',
        content: `
          export async function selectRoom(id: string) {
            const { useRoomStore: getRoomStore } = await import('@/modules/rooms/stores/room')
            const roomStore = getRoomStore()
            roomStore.selectedRoom = id
          }
        `,
      },
    ])

    // The binding is the local name `getRoomStore`, not `useRoomStore: getRoomStore`.
    expect([...found]).toEqual([
      ['src/modules/chat/composables/useRoomSelection.ts -> getRoomStore', 1],
    ])
  })

  it('does not count an unrelated same-named local object from another scope', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/profile/components/RoomLabel.vue',
        content: `
          <script setup lang="ts">
          import { useRoomStore } from '@/modules/rooms/stores/room'

          export function roomName(roomId: string) {
            const store = useRoomStore()
            return store.rooms.find((r) => r.id === roomId)?.name
          }

          export function clearLocalSelection() {
            const store = { selectedRoom: null as string | null }
            store.selectedRoom = null
          }
          </script>
        `,
      },
    ])

    expect([...found]).toEqual([])
  })

  it('flags bare destructured array mutations', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/rooms/composables/useDwellerRoster.ts',
        content: `
          import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
          export function repoint(item: Dweller) {
            const { dwellers } = useDwellerStore()
            dwellers.push(item)
            dwellers.splice(0, 1)
            dwellers.sort(byLevel)
          }
        `,
      },
    ])

    expect(found.get('src/modules/rooms/composables/useDwellerRoster.ts -> useDwellerStore')).toBe(3)
  })

  it('flags a $patch call on another module\'s store', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/chat/components/QuickBuild.vue',
        content: `
          <script setup lang="ts">
          import { useRoomStore } from '@/modules/rooms/stores/room'
          const roomStore = useRoomStore()
          function clearSelection() {
            roomStore.$patch({ selectedRoom: null })
          }
          </script>
        `,
      },
    ])

    expect([...found]).toEqual([['src/modules/chat/components/QuickBuild.vue -> useRoomStore', 1]])
  })

  it('flags a bare .pop() on a destructured store array', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/rooms/composables/useDwellerRoster.ts',
        content: `
          import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
          export function dropLast() {
            const { dwellers } = useDwellerStore()
            dwellers.pop()
          }
        `,
      },
    ])

    expect(found.get('src/modules/rooms/composables/useDwellerRoster.ts -> useDwellerStore')).toBe(1)
  })

  it('flags an .unshift() on a store ref across modules', () => {
    const found = scanCrossStoreWrites([
      {
        path: 'src/modules/chat/composables/useChatActions.ts',
        content: `
          import { storeToRefs } from 'pinia'
          import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
          const dwellerStore = useDwellerStore()
          const { filter } = storeToRefs(dwellerStore)
          filter.value.dwellers.unshift(entry)
        `,
      },
    ])

    expect(found.get('src/modules/chat/composables/useChatActions.ts -> useDwellerStore')).toBe(1)
  })
})
