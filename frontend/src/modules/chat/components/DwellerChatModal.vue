<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import DwellerChat from './DwellerChat.vue'
import { isMature, type Dweller } from '@/modules/dwellers/models/dweller'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { DialogDescription } from '@/core/components/ui/dialog'

const props = defineProps<{
  dwellerId: string
  vaultId?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()

const dweller = ref<Dweller | null>(null)
const username = computed(() => authStore.user?.username || 'User')
const vaultId = computed(() => props.vaultId ?? dweller.value?.vault?.id ?? null)
const fullscreenTo = computed<RouteLocationRaw>(() => ({
  name: 'DwellerChatPage',
  params: { id: props.dwellerId },
  query: {},
}))

const title = computed(() => {
  if (!dweller.value) return 'Conversation'
  return `${dweller.value.first_name} ${dweller.value.last_name ?? ''}`.trim()
})

// Fetch the dweller and pass its vault ID to chat actions without changing the selected vault.
const { run: runLoadDweller, isLoading } = useAsyncAction(
  async (currentDwellerId: string, token: string) => {
    const requestedUserId = authStore.user?.id
    const result = await dwellerStore.fetchDwellerDetails(currentDwellerId, token)
    if (!result) throw new Error('Failed to fetch dweller data')
    if (!authStore.token || (requestedUserId && requestedUserId !== authStore.user?.id)) {
      return result
    }

    dweller.value = result
    return result
  },
  { context: 'Error fetching dweller data', showToast: false }
)

onMounted(async () => {
  if (authStore.token) await runLoadDweller(props.dwellerId, authStore.token)
})

watch(
  () => authStore.token,
  (token) => {
    if (!token) {
      dweller.value = null
      emit('close')
    }
  },
  { flush: 'sync' }
)

watch(
  () => authStore.user?.id,
  (userId, previousUserId) => {
    if (previousUserId && userId !== previousUserId) {
      dweller.value = null
      emit('close')
    }
  },
  { flush: 'sync' }
)
</script>

<template>
  <!-- Boxed dialog with the shared close X and an adjacent full-page action. -->
  <TerminalModal
    :open="true"
    :title="title"
    size="3xl"
    max-height="80"
    :fullscreen-to="fullscreenTo"
    header-class="flex flex-shrink-0 flex-row items-center justify-between gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
    @close="emit('close')"
  >
    <template #header-extra>
      <DialogDescription class="sr-only">Conversation with {{ title }}</DialogDescription>
    </template>

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
        :is-dead="dweller.is_dead"
        :is-permanently-dead="dweller.is_permanently_dead"
      />
      <div v-else class="flex flex-1 items-center justify-center text-theme-primary/60">
        <p>Dweller information unavailable.</p>
      </div>
    </div>
  </TerminalModal>
</template>
