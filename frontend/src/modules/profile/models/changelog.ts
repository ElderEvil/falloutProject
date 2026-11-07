import type { ChangeEntry } from '../services/changelogService'

/**
 * Group one changelog entry's changes by category, preserving first-seen order.
 *
 * The returned tuple list is directly usable in `v-for="[category, changes] in ..."`.
 */
export function groupChangesByCategory(changes: ChangeEntry[]): Array<[string, ChangeEntry[]]> {
  const grouped = new Map<string, ChangeEntry[]>()

  for (const change of changes) {
    const bucket = grouped.get(change.category)
    if (bucket) {
      bucket.push(change)
    } else {
      grouped.set(change.category, [change])
    }
  }

  return Array.from(grouped.entries())
}
