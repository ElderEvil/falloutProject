<script setup lang="ts">
import { ref, watch } from 'vue'
import { vaultNumberSchema } from '../schemas/vault'
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

watch(modelValue, () => validate())

function _parseNumber(value: string): number {
  const parsed = parseInt(value, 10)
  if (isNaN(parsed)) throw new Error('Vault number must be a number')
  return parsed
}

function validate(): void {
  error.value = null
  if (!modelValue.value) {
    error.value = 'Vault number is required'
    return
  }
  try {
    vaultNumberSchema.parse({ number: _parseNumber(modelValue.value) })
  } catch (err: any) {
    error.value = err.errors?.[0]?.message || 'Invalid vault number'
  }
}

function isValid(): boolean {
  error.value = null
  if (!modelValue.value) {
    error.value = 'Vault number is required'
    return false
  }
  try {
    vaultNumberSchema.parse({ number: _parseNumber(modelValue.value) })
    return true
  } catch (err: any) {
    error.value = err.errors?.[0]?.message || 'Invalid vault number'
    return false
  }
}

defineExpose({ isValid })
</script>

<template>
  <div class="w-full">
    <Label for="vault-number" class="mb-1 text-sm font-medium text-theme-primary/70">
      Vault Number
    </Label>
    <Input
      id="vault-number"
      v-model="modelValue"
      type="number"
      placeholder="Vault Number (1-999)"
      class="grow h-auto w-full rounded border-2 bg-surface-sunken px-4 py-2 text-terminal-green placeholder:text-theme-primary/40"
      :class="error ? 'border-danger focus:border-danger' : 'border-theme-primary/50 focus:border-theme-primary'"
    />
    <p v-if="error" class="mt-1 text-xs text-danger">{{ error }}</p>
  </div>
</template>

<style scoped>
:deep(input[type='number']) {
  color-scheme: dark;
}
</style>
