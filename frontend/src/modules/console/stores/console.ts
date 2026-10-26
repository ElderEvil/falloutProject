import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { consoleApi, type ConsoleManifest, type ConsoleResult } from '../api/consoleApi'
import { parseCommand } from '../utils/commands'

interface OutputLine {
  text: string
  kind: 'echo' | 'error' | 'output'
  to?: string
}

export const useConsoleStore = defineStore('admin-console', () => {
  const auth = useAuthStore()
  const open = ref(false)
  const busy = ref(false)
  const manifest = ref<ConsoleManifest | null>(null)
  const lines = ref<OutputLine[]>([])
  const historyKey = computed(() => `admin-console-history:${auth.user?.id ?? 'signed-out'}`)
  const history = useLocalStorage<string[]>(historyKey, [])
  let generation = 0

  function append(entries: OutputLine[]): void {
    lines.value = [...lines.value, ...entries].slice(-500)
  }

  function report(error: unknown): void {
    console.error('Admin console request failed', error)
    append([{ text: getErrorMessage(error), kind: 'error' }])
  }

  function output(result: ConsoleResult): void {
    append([
      ...result.lines.map((text): OutputLine => ({ text, kind: result.ok ? 'output' : 'error' })),
      ...(result.links ?? []).map((link): OutputLine => ({
        text: link.label,
        to: link.to,
        kind: 'output',
      })),
    ])
  }

  async function show(): Promise<void> {
    if (!auth.isAuthenticated || !auth.isSuperuser) return
    open.value = true
    if (manifest.value || busy.value) return
    const request = generation
    busy.value = true
    try {
      const result = await consoleApi.manifest()
      if (request !== generation) return
      manifest.value = result
      append([
        { text: 'Console ready. Type help. Tab completes; ↑ / ↓ recall commands.', kind: 'output' },
      ])
    } catch (error) {
      if (request === generation) report(error)
    } finally {
      if (request === generation) busy.value = false
    }
  }

  async function execute(input: string, vaultId?: string): Promise<void> {
    if (
      !auth.isAuthenticated ||
      !auth.isSuperuser ||
      busy.value ||
      !manifest.value ||
      !input.trim()
    )
      return
    const request = generation
    history.value = [...history.value.filter((item) => item !== input), input].slice(-100)
    append([{ text: `> ${input}`, kind: 'echo' }])
    busy.value = true
    try {
      const result = await consoleApi.execute(parseCommand(input, manifest.value, vaultId))
      if (request === generation) output(result)
    } catch (error) {
      if (request === generation) report(error)
    } finally {
      if (request === generation) busy.value = false
    }
  }

  function reset(): void {
    generation += 1
    open.value = false
    busy.value = false
    manifest.value = null
    lines.value = []
  }

  watch([() => auth.user?.id, () => auth.isSuperuser, () => auth.isAuthenticated], reset, {
    flush: 'sync',
  })

  return { open, busy, manifest, lines, history, show, execute, reset }
})
