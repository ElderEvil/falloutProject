<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import { useDwellerStore } from '../stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'

interface Props {
  vaultId: string
}

const props = defineProps<Props>()
const dwellerStore = useDwellerStore()
const authStore = useAuthStore()

const unassigningAll = ref(false)
const autoAssigning = ref(false)
const showConfirmDialog = ref(false)

const handleUnassignAll = async () => {
  if (!authStore.token) return

  unassigningAll.value = true
  try {
    await dwellerStore.unassignAllDwellers(props.vaultId, authStore.token)
  } finally {
    unassigningAll.value = false
    showConfirmDialog.value = false
  }
}

const handleAutoAssignAll = async () => {
  if (!authStore.token) return

  autoAssigning.value = true
  try {
    await dwellerStore.autoAssignAllRooms(props.vaultId, authStore.token)
  } finally {
    autoAssigning.value = false
  }
}
</script>

<template>
  <div class="bulk-actions-inline">
    <UButton
      variant="danger"
      size="xs"
      @click="showConfirmDialog = true"
      :loading="unassigningAll"
    >
      <Icon icon="mdi:account-remove" class="h-4 w-4 mr-1" />
      Unassign All
    </UButton>

    <UButton
      variant="primary"
      size="xs"
      @click="handleAutoAssignAll"
      :loading="autoAssigning"
    >
      <Icon icon="mdi:auto-mode" class="h-4 w-4 mr-1" />
      Auto-Assign All Rooms
    </UButton>

    <!-- Confirmation Dialog -->
    <Teleport to="body">
      <div v-if="showConfirmDialog" class="confirmation-overlay" @click="showConfirmDialog = false">
        <div class="confirmation-dialog" @click.stop>
          <div class="flicker">
            <h3>Unassign All Dwellers?</h3>
            <p>This will remove all dwellers from their current room assignments.</p>
            <div class="dialog-actions">
              <UButton variant="secondary" @click="showConfirmDialog = false">Cancel</UButton>
              <UButton variant="danger" @click="handleUnassignAll" :loading="unassigningAll">Confirm</UButton>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.bulk-actions-inline {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.confirmation-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirmation-dialog {
  background: rgba(0, 0, 0, 0.95);
  border: 2px solid var(--color-theme-primary);
  border-radius: 0.5rem;
  padding: 2rem;
  max-width: 400px;
  box-shadow: 0 0 30px var(--color-theme-glow);
}

.confirmation-dialog h3 {
  color: var(--color-theme-primary);
  margin-bottom: 1rem;
  font-size: 1.25rem;
  font-weight: bold;
  text-transform: uppercase;
}

.confirmation-dialog p {
  color: var(--color-theme-primary);
  opacity: 0.8;
  margin-bottom: 1.5rem;
}

.dialog-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.flicker {
  animation: flicker 0.15s infinite;
}

@keyframes flicker {
  0% { opacity: 0.97; }
  5% { opacity: 0.95; }
  10% { opacity: 0.9; }
  15% { opacity: 0.95; }
  20% { opacity: 0.98; }
  25% { opacity: 0.95; }
  30% { opacity: 0.9; }
  35% { opacity: 0.95; }
  40% { opacity: 0.98; }
  45% { opacity: 1; }
  50% { opacity: 0.98; }
  55% { opacity: 0.95; }
  60% { opacity: 0.9; }
  65% { opacity: 0.95; }
  70% { opacity: 0.98; }
  75% { opacity: 0.95; }
  80% { opacity: 0.9; }
  85% { opacity: 0.95; }
  90% { opacity: 0.98; }
  95% { opacity: 0.95; }
  100% { opacity: 0.98; }
}
</style>
