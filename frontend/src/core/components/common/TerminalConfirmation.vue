<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Alert, AlertDescription, AlertTitle } from '@/core/components/ui/alert'
import TerminalModal from './TerminalModal.vue'
import TerminalModalActions from './TerminalModalActions.vue'
import { DialogDescription } from '@/core/components/ui/dialog'

withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel: string
    /** Failure reason from the owning store; the dialog stays open while it is set. */
    error?: string | null
  }>(),
  { error: null }
)
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <TerminalModal :open="open" :title="title" size="sm" @close="emit('cancel')">
    <DialogDescription class="p-6 text-theme-primary">{{ message }}</DialogDescription>
    <div v-if="error" class="px-6 pb-6">
      <Alert variant="destructive">
        <Icon icon="mdi:alert-circle-outline" />
        <AlertTitle>CONFIRMATION REFUSED</AlertTitle>
        <AlertDescription>{{ error }}</AlertDescription>
      </Alert>
    </div>
    <template #footer>
      <TerminalModalActions
        cancel-label="Cancel"
        :confirm-label="confirmLabel"
        @cancel="emit('cancel')"
        @confirm="emit('confirm')"
      />
    </template>
  </TerminalModal>
</template>
