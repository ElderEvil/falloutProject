<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import { useRoute, RouterLink } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Input } from '@/core/components/ui/input'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/core/components/ui/dialog'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useConsoleStore } from '../stores/console'
import { completeCommand } from '../utils/commands'

const terminal = useConsoleStore()
const route = useRoute()
const vaults = useVaultStore()
const input = ref('')
const output = ref<HTMLElement | null>(null)
const commandForm = ref<HTMLElement | null>(null)
const vaultId = computed(() =>
  route.path.startsWith('/vault/') && typeof route.params.id === 'string'
    ? route.params.id
    : undefined
)
const vaultName = computed(
  () =>
    vaults.vaults.find((vault) => vault.id === vaultId.value)?.number ?? vaultId.value?.slice(0, 8)
)
let historyIndex = 0
let draft = ''
let completions: string[] = []
let completionIndex = 0

async function focusInput(): Promise<void> {
  await nextTick()
  commandForm.value?.querySelector('input')?.focus()
}

function toggle(): void {
  if (terminal.open) terminal.open = false
  else void terminal.show()
}

useEventListener(window, 'keydown', (event: KeyboardEvent) => {
  if (
    event.code !== 'Backquote' ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.repeat ||
    event.isComposing
  )
    return
  const target = event.target
  if (
    target instanceof HTMLElement &&
    target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])') &&
    !commandForm.value?.contains(target)
  )
    return
  event.preventDefault()
  toggle()
})

watch(
  () => terminal.lines,
  async () => {
    await nextTick()
    if (output.value) output.value.scrollTop = output.value.scrollHeight
  }
)
watch(vaultId, () => terminal.reset(), { flush: 'sync' })
watch(
  () => terminal.busy,
  (busy) => {
    if (!busy && terminal.open) void focusInput()
  }
)
watch(
  () => terminal.open,
  (open) => {
    if (open) {
      historyIndex = terminal.history.length
      void focusInput()
    }
  }
)

async function submit(): Promise<void> {
  const command = input.value.trim()
  input.value = ''
  completions = []
  await terminal.execute(command, vaultId.value)
  historyIndex = terminal.history.length
  await focusInput()
}

function onInputKey(event: KeyboardEvent): void {
  if (event.key === 'Tab') {
    event.preventDefault()
    if (!terminal.manifest) return
    if (!completions.includes(input.value)) {
      completions = completeCommand(input.value, terminal.manifest)
      completionIndex = 0
    }
    if (completions.length) input.value = completions[completionIndex++ % completions.length]!
  } else if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
    event.preventDefault()
    if (historyIndex === terminal.history.length) draft = input.value
    historyIndex = Math.max(
      0,
      Math.min(terminal.history.length, historyIndex + (event.key === 'ArrowUp' ? -1 : 1))
    )
    input.value = terminal.history[historyIndex] ?? draft
  } else completions = []
}
</script>

<template>
  <Button
    variant="outline"
    size="sm"
    class="fixed bottom-3 left-3 z-40 gap-2 bg-surface-canvas font-mono text-xs"
    aria-label="Open admin terminal"
    @click="toggle"
  >
    <Icon icon="mdi:console" class="size-4" /> CONSOLE <kbd class="opacity-50">`</kbd>
  </Button>
  <Dialog v-model:open="terminal.open">
    <DialogContent
      class="admin-terminal top-0 left-0 z-[110] flex h-[65dvh] max-h-[850px] w-full max-w-none translate-x-0 translate-y-0 flex-col gap-0 rounded-none border-b-2 border-theme-primary bg-surface-canvas p-0 font-mono text-theme-primary sm:max-w-none"
      :show-close-button="false"
      @interact-outside.prevent
      @open-auto-focus.prevent="focusInput"
    >
      <header
        class="flex items-center justify-between gap-3 border-b border-theme-primary/30 px-4 py-3 sm:px-6"
      >
        <div>
          <DialogTitle class="flex items-center gap-2 text-sm font-bold uppercase tracking-widest"
            ><Icon icon="mdi:console" class="size-5" /> Overseer command console</DialogTitle
          >
          <DialogDescription class="mt-1 text-xs text-theme-primary/60"
            >ADMIN ACCESS · {{ vaultId ? `VAULT ${vaultName}` : 'NO VAULT SELECTED' }} · ESC TO
            CLOSE</DialogDescription
          >
        </div>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Close admin terminal"
          @click="terminal.open = false"
          ><Icon icon="mdi:close" class="size-5"
        /></Button>
      </header>
      <div
        ref="output"
        role="log"
        aria-label="Console output"
        aria-live="polite"
        class="min-h-0 flex-1 overflow-y-auto px-4 py-4 text-xs leading-relaxed sm:px-6 sm:text-sm"
      >
        <p class="mb-3 text-theme-primary/60">VAULT-TEC OPERATIONS / AUTHORIZED PERSONNEL ONLY</p>
        <p
          v-for="(line, index) in terminal.lines"
          :key="index"
          class="whitespace-pre-wrap break-words"
          :class="
            line.kind === 'error'
              ? 'text-danger'
              : line.kind === 'echo'
                ? 'mt-3 text-theme-primary/60'
                : ''
          "
        >
          <RouterLink
            v-if="line.to"
            :to="line.to"
            class="underline underline-offset-4"
            @click="terminal.open = false"
            >{{ line.text }} →</RouterLink
          ><template v-else>{{ line.text }}</template>
        </p>
        <p v-if="terminal.busy" role="status" class="mt-3 flex items-center gap-2">
          <Icon icon="mdi:loading" class="size-4 animate-spin" /> Processing…
        </p>
      </div>
      <details
        v-if="terminal.manifest"
        class="border-t border-theme-primary/20 px-4 py-2 text-xs sm:px-6"
      >
        <summary class="cursor-pointer text-theme-primary/70">Expedition site IDs</summary>
        <ul class="mt-2 grid max-h-24 gap-1 overflow-y-auto sm:grid-cols-2">
          <li v-for="site in terminal.manifest.sites" :key="site.id">
            {{ site.id }} · level {{ site.min_level }}+
          </li>
        </ul>
      </details>
      <form
        ref="commandForm"
        class="flex items-center gap-2 border-t border-theme-primary/40 bg-surface-raised px-4 py-3 sm:px-6"
        @submit.prevent="submit"
      >
        <span aria-hidden="true" class="text-sm"
          >{{ vaultId ? `vault${vaultName}` : 'overseer' }}&gt;</span
        >
        <!-- @vue-ignore -->
        <Input
          v-model="input"
          aria-label="Admin command"
          autocomplete="off"
          :disabled="terminal.busy || !terminal.manifest"
          placeholder="help"
          class="border-none bg-transparent font-mono shadow-none focus-visible:ring-0"
          @keydown="onInputKey"
        />
        <Button
          type="submit"
          variant="ghost"
          size="sm"
          :disabled="terminal.busy || !terminal.manifest || !input.trim()"
          aria-label="Run command"
          ><Icon icon="mdi:keyboard-return" class="size-5"
        /></Button>
      </form>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
@reference '../../../assets/tailwind.css';
.admin-terminal {
  box-shadow: 0 8px 40px color-mix(in srgb, var(--color-theme-primary) 15%, transparent);
}
.admin-terminal[data-state='open'] {
  animation: terminal-drop 180ms ease-out;
}
@keyframes terminal-drop {
  from {
    transform: translateY(-100%);
  }
  to {
    transform: translateY(0);
  }
}
@media (prefers-reduced-motion: reduce) {
  .admin-terminal[data-state='open'] {
    animation: none;
  }
}
</style>
