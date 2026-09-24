<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/core/components/ui/dialog'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useExitRequestStore } from '../../stores/exitRequests'

const vaultStore = useVaultStore()
const store = useExitRequestStore()

const isOpen = ref(false)
const isDeciding = ref(false)

const current = computed(() => store.requests[0] ?? null)

watch(
  current,
  (request) => {
    isOpen.value = request !== null
  },
  { immediate: true }
)

const refresh = async () => {
  if (!vaultStore.activeVaultId) return
  await store.load(vaultStore.activeVaultId)
}

onMounted(refresh)
watch(() => vaultStore.activeVaultId, refresh)

const decide = async (grant: boolean) => {
  const request = current.value
  const vaultId = vaultStore.activeVaultId
  if (!request || !vaultId) return

  isDeciding.value = true
  try {
    if (grant) await store.grant(vaultId, request.dweller_id)
    else await store.refuse(vaultId, request.dweller_id)
  } finally {
    isDeciding.value = false
  }
}

const close = () => {
  isOpen.value = false
}
</script>

<template>
  <Dialog :open="isOpen" @update:open="(open) => { if (!open) close() }">
    <DialogContent
      class="flex max-h-[65vh] w-full max-w-md flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-md"
    >
      <DialogHeader
        class="flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
      >
        <DialogTitle class="text-2xl font-bold text-theme-primary terminal-glow">Someone Wants Out</DialogTitle>
      </DialogHeader>

      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
        <div v-if="current" class="exit-request-modal">
          <div class="subject">
            <Icon icon="mdi:exit-run" class="subject-icon" />
            <div class="subject-details">
              <span class="subject-name">{{ current.dweller_name }}</span>
              <span class="subject-meta">
                Level {{ current.level }} · Happiness {{ current.happiness }}/100
              </span>
            </div>
          </div>

          <p class="description">
            They have asked to go outside. The vault can refuse them, but it cannot keep them forever —
            and if you let them go, they are not coming back.
          </p>

          <div class="modal-actions">
            <Button variant="secondary" :disabled="isDeciding" @click="close"> Decide Later </Button>
            <Button variant="secondary" :disabled="isDeciding" @click="decide(false)"> Refuse </Button>
            <Button variant="destructive" :disabled="isDeciding" @click="decide(true)">
              Let Them Go
            </Button>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.exit-request-modal {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.subject {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
}

.subject-icon {
  font-size: 1.75rem;
  color: var(--color-danger);
}

.subject-details {
  display: flex;
  flex-direction: column;
}

.subject-name {
  font-weight: 700;
  color: var(--color-theme-primary);
}

.subject-meta {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.description {
  color: var(--color-theme-primary);
  opacity: 0.85;
  font-size: 0.875rem;
  line-height: 1.5;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}
</style>
