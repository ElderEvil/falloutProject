<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { getCurrentInstance, onMounted, watch } from 'vue'
import { SwitchRoot, SwitchThumb } from 'reka-ui'
import { cn } from '@/core/utils/cn'

const props = defineProps<{
  id?: string
  checked?: boolean
  disabled?: boolean
  class?: HTMLAttributes['class']
  ariaLabel?: string
  /** Kebab alias so `:aria-label` template usage typechecks; Vue camelizes it onto ariaLabel. */
  'aria-label'?: string
}>()

const emit = defineEmits<{
  'update:checked': [value: boolean]
}>()

// Static attrs on the template root trip strictTemplates' object-literal
// check, so data-slot rides a script-bound object instead (same DOM result).
const rootAttrs = { 'data-slot': 'switch' } as const
const thumbAttrs = { 'data-slot': 'switch-thumb' } as const

// Reka's SwitchRoot only reads aria-label from its own $attrs, so a declared
// wrapper prop never reaches the DOM through binding. Apply it imperatively.
// ($el can be a leading template comment when the root is a fragment, so
// resolve to the actual switch button first.)
function switchElement(): HTMLElement | undefined {
  const el = getCurrentInstance()?.proxy?.$el as HTMLElement | undefined
  if (el instanceof HTMLElement) return el.querySelector<HTMLElement>('[data-slot="switch"]') ?? el
  const next = (el as ChildNode | undefined)?.nextSibling
  return next instanceof HTMLElement ? next : undefined
}

function applyAriaLabel() {
  const label = props.ariaLabel
  if (switchEl === undefined) return
  if (label === undefined) switchEl.removeAttribute('aria-label')
  else switchEl.setAttribute('aria-label', label)
}

let switchEl: HTMLElement | undefined
onMounted(() => {
  switchEl = switchElement()
  applyAriaLabel()
})
watch(
  () => props.ariaLabel,
  applyAriaLabel,
)
</script>

<template>
  <SwitchRoot
    v-bind="rootAttrs"
    :id="id"
    :model-value="checked"
    :disabled="disabled"
    :class="cn(
      'inline-flex h-7 w-14 shrink-0 cursor-pointer items-center rounded-full border-2 border-theme-primary bg-muted transition-colors duration-300 outline-none select-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:border-ring disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-theme-primary',
      props.class,
    )"
    @update:model-value="(value: boolean) => emit('update:checked', value)"
  >
    <SwitchThumb
      v-bind="thumbAttrs"
      :class="cn(
        'pointer-events-none block size-5 rounded-full bg-theme-primary transition-transform duration-300 data-[state=checked]:translate-x-7 data-[state=checked]:bg-background',
      )"
    />
  </SwitchRoot>
</template>
