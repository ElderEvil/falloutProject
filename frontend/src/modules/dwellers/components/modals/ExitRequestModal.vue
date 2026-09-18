<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import UModal from '@/core/components/ui/UModal.vue'
import UButton from '@/core/components/ui/UButton.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useExitRequestStore } from '../../stores/exitRequests'

const authStore = useAuthStore()
const vaultStore = useVaultStore()
const store = useExitRequestStore()

const snoozed = ref<string[]>([])
const isDeciding = ref(false)

const current = computed(
  () => store.requests.find((request) => !snoozed.value.includes(request.dweller_id)) ?? null
)
const isOpen = computed(() => current.value !== null)

const refresh = async () => {
  if (!vaultStore.activeVaultId || !authStore.token) return
  await store.load(vaultStore.activeVaultId, authStore.token)
}

onMounted(refresh)
watch(() => vaultStore.activeVaultId, refresh)

const decide = async (grant: boolean) => {
  const request = current.value
  const vaultId = vaultStore.activeVaultId
  if (!request || !vaultId || !authStore.token) return

  isDeciding.value = true
  try {
    if (grant) await store.grant(vaultId, request.dweller_id, authStore.token)
    else await store.refuse(vaultId, request.dweller_id, authStore.token)
  } finally {
    isDeciding.value = false
  }
}

const decideLater = () => {
  if (current.value) snoozed.value = [...snoozed.value, current.value.dweller_id]
}

const close = () => {
  decideLater()
}
</script>

<template>
  <UModal :model-value="isOpen" title="Someone Wants Out" size="md" @close="close">
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
        <UButton variant="secondary" :disabled="isDeciding" @click="decideLater">
          Decide Later
        </UButton>
        <UButton variant="secondary" :disabled="isDeciding" @click="decide(false)"> Refuse </UButton>
        <UButton variant="danger" :disabled="isDeciding" @click="decide(true)">
          Let Them Go
        </UButton>
      </div>
    </div>
  </UModal>
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
