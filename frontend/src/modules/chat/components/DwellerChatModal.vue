<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import DwellerChat from './DwellerChat.vue'
import { isMature, type Dweller } from '@/modules/dwellers/models/dweller'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { Button } from '@/core/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/core/components/ui/dialog'

const props = defineProps<{
  dwellerId: string
  vaultId?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()
const vaultStore = useVaultStore()

const dweller = ref<Dweller | null>(null)
const username = ref(authStore.user?.username || 'User')
const vaultId = computed(() => props.vaultId ?? dweller.value?.vault?.id ?? null)

const title = computed(() => {
  if (!dweller.value) return 'Conversation'
  return `${dweller.value.first_name} ${dweller.value.last_name ?? ''}`.trim()
})

// Mirrors DwellerChatPage's data loading: fetch the dweller, derive the vault,
// and hydrate the vault store so chat actions can refresh it after the fact.
const { run: runLoadDweller, isLoading } = useAsyncAction(
  async (currentDwellerId: string, token: string) => {
    const result = await dwellerStore.fetchDwellerDetails(currentDwellerId, token)
    if (!result) throw new Error('Failed to fetch dweller data')

    dweller.value = result
    if (result.vault?.id && vaultStore.activeVaultId !== result.vault.id) {
      await vaultStore.loadVault(result.vault.id, token)
    }
    return result
  },
  { context: 'Error fetching dweller data', showToast: false }
)

onMounted(async () => {
  if (authStore.token) await runLoadDweller(props.dwellerId, authStore.token)
})
</script>

<template>
  <!-- Boxed dialog with a header bar: the title carries the dweller's full name
       (the chat's identity line shows the first name only) and the close button
       emits directly instead of relying on the dialog's dismiss chain. -->
  <Dialog
    :open="true"
    @update:open="
      (open) => {
        if (!open) emit('close')
      }
    "
  >
    <DialogContent
      :show-close-button="false"
      class="flex max-h-[80vh] w-full max-w-3xl flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-3xl"
    >
      <DialogHeader
        class="flex flex-shrink-0 flex-row items-center justify-between gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
      >
        <DialogTitle class="text-2xl font-bold text-theme-primary terminal-glow">{{
          title
        }}</DialogTitle>
        <DialogDescription class="sr-only">Conversation with {{ title }}</DialogDescription>
        <Button variant="ghost" size="icon-sm" aria-label="Close chat" @click="emit('close')">
          <Icon icon="mdi:close" class="h-4 w-4" />
        </Button>
      </DialogHeader>

      <div class="flex min-h-0 flex-1 flex-col p-5">
        <TerminalLoadingState v-if="isLoading" message="Establishing connection to dweller..." />
        <DwellerChat
          v-else-if="dweller"
          class="min-h-0 [&_.chat-messages]:min-h-0"
          :dweller-id="dwellerId"
          :dweller-name="dweller.first_name"
          :username="username"
          :dweller-avatar="dweller.thumbnail_url ?? undefined"
          :vault-id="vaultId"
          :dweller-status="dweller.status"
          :room-name="dweller.room?.name"
          :dweller-can-explore="isMature(dweller)"
        />
        <div v-else class="flex flex-1 items-center justify-center text-theme-primary/60">
          <p>Dweller information unavailable.</p>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
