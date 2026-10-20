<script setup lang="ts">
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { parseVaultNumber } from '../schemas/vault'
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'

/**
 * VaultNumberField - Terminal-themed vault number input with validation
 *
 * Validates vault numbers (1-999) using the shared Zod schema.
 * Exposes isValid() for parent validation before vault creation.
 */

const modelValue = defineModel<string>({ required: true })
const error = ref<string | null>(null)
const numberInput = ref<InstanceType<typeof Input> | null>(null)

watch(modelValue, validate)

function randomize(): void {
  modelValue.value = String(Math.floor(Math.random() * 999) + 1)
}

function validate(): boolean {
  error.value = null
  if (!modelValue.value) {
    error.value = 'Vault number is required'
    return false
  }
  try {
    parseVaultNumber(String(modelValue.value))
    return true
  } catch {
    error.value = 'Invalid vault number'
    return false
  }
}

// Parent-driven autofocus: bring the field into view, then move the caret
// without letting the browser jump-scroll and cut the smooth scroll short.
function focus(): void {
  const inputEl = numberInput.value?.$el as HTMLInputElement | undefined
  if (!inputEl) return
  inputEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
  inputEl.focus({ preventScroll: true })
}

defineExpose({ isValid: validate, focus })
</script>

<template>
  <div class="w-full">
    <Label for="vault-number" class="mb-1 text-sm font-medium text-theme-primary/70">
      Vault Number
    </Label>
    <div class="flex items-stretch gap-2">
      <Input
        id="vault-number"
        ref="numberInput"
        v-model="modelValue"
        type="number"
        placeholder="1–999"
        class="grow h-auto min-w-0 w-full rounded border-2 bg-surface-sunken px-4 py-2 text-terminal-green placeholder:text-theme-primary/40 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        :class="
          error
            ? 'border-danger focus:border-danger'
            : 'border-theme-primary/50 focus:border-theme-primary'
        "
      />
      <Button
        type="button"
        variant="outline"
        class="h-auto shrink-0"
        aria-label="Random vault number"
        @click="randomize"
      >
        <Icon icon="mdi:dice-multiple-outline" class="size-4" :ariaHidden="true" />
        Random
      </Button>
    </div>
    <p v-if="error" class="mt-1 text-xs text-danger">{{ error }}</p>
  </div>
</template>
