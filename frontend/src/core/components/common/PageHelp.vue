<script setup lang="ts">
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

defineProps<{ title: string }>()
</script>

<template>
  <Dialog>
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
