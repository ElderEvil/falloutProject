<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from '@/core/components/ui/dialog'
import { useBlockingOverlay } from '@/core/composables/useBlockingOverlay'

defineProps<{ title: string }>()

// The dialog is uncontrolled by default; bind it so the help panel can register
// as an attention owner like every other dialog.
const open = ref(false)
useBlockingOverlay(open)
</script>

<template>
  <Dialog v-model:open="open">
    <DialogTrigger as-child>
      <Button variant="ghost" size="sm" :aria-label="`About ${title}`">
        <Icon icon="mdi:information-outline" />
        <span>About</span>
      </Button>
    </DialogTrigger>
    <DialogContent class="max-h-[85dvh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>About {{ title }}</DialogTitle>
        <DialogDescription>How it works and what you can control.</DialogDescription>
      </DialogHeader>
      <div class="space-y-4 text-sm leading-relaxed text-theme-primary/80">
        <slot />
      </div>
    </DialogContent>
  </Dialog>
</template>
