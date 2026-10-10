<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/core/components/ui/dialog'

/** Width variants observed across the migrated modal shells. */
type TerminalModalSize = 'sm' | 'md' | 'xl' | '3xl' | '5xl' | '6xl'
/** Max-height variants observed across the migrated modal shells (in vh). */
type TerminalModalMaxHeight = '60' | '65' | '75' | '80' | '90'

/**
 * Shared terminal modal shell. Owns the Dialog/DialogContent sizing plus the
 * canonical CRT header/footer chips so callers only supply content. The
 * optional `*Class` props exist because a handful of shells legitimately vary
 * (tighter header gap, extra right padding, a non-justified footer); passing
 * one replaces the canonical chip verbatim.
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    icon?: string
    iconClass?: string
    size?: TerminalModalSize
    maxHeight?: TerminalModalMaxHeight
    showClose?: boolean
    showFooter?: boolean
    headerClass?: string
    titleClass?: string
    footerClass?: string
    contentClass?: string
    titleAsChild?: boolean
    /**
     * When set, the default slot and footer are wrapped in this class (the
     * scrollable body). Some shells (PartySelection) nest the footer inside the
     * scroll region rather than pinning it as a sibling.
     */
    bodyClass?: string
  }>(),
  {
    size: 'md',
    maxHeight: '75',
    showClose: true,
    showFooter: true,
    titleAsChild: false,
    iconClass: 'h-8 w-8 text-theme-primary terminal-glow',
  }
)

const emit = defineEmits<{
  'update:open': [open: boolean]
  close: []
}>()

// Literal class strings keep every variant statically visible to Tailwind.
const MAX_HEIGHT_CLASSES: Record<TerminalModalMaxHeight, string> = {
  '60': 'max-h-[60vh]',
  '65': 'max-h-[65vh]',
  '75': 'max-h-[75vh]',
  '80': 'max-h-[80vh]',
  '90': 'max-h-[90vh]',
}

const SIZE_CLASSES: Record<TerminalModalSize, string> = {
  sm: 'max-w-sm sm:max-w-sm',
  md: 'max-w-md sm:max-w-md',
  xl: 'max-w-xl sm:max-w-xl',
  '3xl': 'max-w-3xl sm:max-w-3xl',
  '5xl': 'max-w-5xl sm:max-w-5xl',
  '6xl': 'max-w-6xl sm:max-w-6xl',
}

const HEADER_CLASS =
  'flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4'
const FOOTER_CLASS =
  'flex-shrink-0 justify-end border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5'
const TITLE_CLASS = 'text-2xl font-bold text-theme-primary terminal-glow'

const contentClasses = computed(() =>
  [
    'flex',
    MAX_HEIGHT_CLASSES[props.maxHeight],
    'w-full',
    SIZE_CLASSES[props.size],
    'flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen',
    props.contentClass,
  ]
    .filter(Boolean)
    .join(' ')
)

const titleClasses = computed(() =>
  props.titleAsChild ? undefined : props.titleClass ?? TITLE_CLASS
)

const handleOpenChange = (open: boolean) => {
  emit('update:open', open)
  if (!open) emit('close')
}
</script>

<template>
  <Dialog :open="open" @update:open="handleOpenChange">
    <DialogContent :show-close-button="showClose" :class="contentClasses">
      <DialogHeader :class="headerClass ?? HEADER_CLASS">
        <Icon v-if="icon" :icon="icon" :class="iconClass" />
        <DialogTitle :as-child="titleAsChild" :class="titleClasses">
          <slot name="title">{{ title }}</slot>
        </DialogTitle>
        <slot name="header-extra" />
      </DialogHeader>

      <slot name="subheader" />

      <div v-if="bodyClass" :class="bodyClass">
        <slot />
        <DialogFooter v-if="showFooter && $slots.footer" :class="footerClass ?? FOOTER_CLASS">
          <slot name="footer" />
        </DialogFooter>
      </div>
      <template v-else>
        <slot />

        <DialogFooter v-if="showFooter && $slots.footer" :class="footerClass ?? FOOTER_CLASS">
          <slot name="footer" />
        </DialogFooter>
      </template>
    </DialogContent>
  </Dialog>
</template>
