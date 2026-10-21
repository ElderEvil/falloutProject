<script setup lang="ts">
import TerminalModal from './TerminalModal.vue'
import TerminalModalActions from './TerminalModalActions.vue'
import { DialogDescription } from '@/core/components/ui/dialog'

defineProps<{ open: boolean; title: string; message: string; confirmLabel: string }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <TerminalModal :open="open" :title="title" size="sm" @close="emit('cancel')">
    <DialogDescription class="p-6 text-theme-primary">{{ message }}</DialogDescription>
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
