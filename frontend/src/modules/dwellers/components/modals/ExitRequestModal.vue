<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useIntervalFn, useLocalStorage } from '@vueuse/core'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { useNow } from '@/core/composables/useNow'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useExitRequestStore } from '../../stores/exitRequests'

const SNOOZE_MS = 60 * 60 * 1000

const vaultStore = useVaultStore()
const store = useExitRequestStore()

const isDeciding = ref(false)
const snoozedUntil = useLocalStorage<number | null>('exitRequestSnoozedUntil', null)
const now = useNow(30_000)

const current = computed(() => store.requests[0] ?? null)
const isSnoozed = computed(
  () => snoozedUntil.value !== null && now.value < snoozedUntil.value
)
const isOpen = computed(() => current.value !== null && !isSnoozed.value)

const refresh = async () => {
  if (!vaultStore.activeVaultId) return
  await store.load(vaultStore.activeVaultId)
}

onMounted(refresh)
watch(() => vaultStore.activeVaultId, refresh)
// The ask is raised server-side on a tick, so the open session has to re-check;
// otherwise the modal only appears after a reload.
useIntervalFn(refresh, 60_000)

const decide = async (grant: boolean) => {
  const request = current.value
  const vaultId = vaultStore.activeVaultId
  if (!request || !vaultId) return

  isDeciding.value = true
  try {
    const decided = grant
      ? await store.grant(vaultId, request.dweller_id)
      : await store.refuse(vaultId, request.dweller_id, request.refusal_happiness_penalty)
    if (decided) decideLater()
  } finally {
    isDeciding.value = false
  }
}

const decideLater = () => {
  snoozedUntil.value = Date.now() + SNOOZE_MS
}
</script>

<template>
  <TerminalModal
    :open="isOpen"
    title="Someone Wants Out"
    size="xl"
    max-height="65"
    @close="decideLater"
  >
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
          They have asked to go outside. Refusing keeps them here: the whole vault loses
          {{ current.refusal_happiness_penalty }} happiness. They will not ask again for a day.
          Letting them go means they are not coming back.
        </p>

        <div class="modal-actions">
          <Button variant="secondary" :disabled="isDeciding" @click="decideLater">
            <Icon icon="mdi:clock-outline" />
            Decide Later
          </Button>
          <Button variant="secondary" :disabled="isDeciding" @click="decide(false)">
            <Icon icon="mdi:hand-back-right-outline" />
            Refuse — vault −{{ current.refusal_happiness_penalty }}
            <Icon icon="mdi:emoticon-sad-outline" />
          </Button>
          <Button variant="destructive" :disabled="isDeciding" @click="decide(true)">
            <Icon icon="mdi:exit-run" />
            Let Them Go
          </Button>
        </div>
      </div>
    </div>
  </TerminalModal>
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
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.75rem;
}
</style>
