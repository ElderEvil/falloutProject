<script setup lang="ts">
import { ref, watch } from 'vue'
import { vaultNumberSchema } from '../schemas/vault'
import { UInput } from '@/core/components/ui'

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
  <UInput
    v-model="modelValue"
    type="number"
    label="Vault Number"
    placeholder="Vault Number (1-999)"
    :error="error || undefined"
    variant="terminal"
    class="grow"
  />
</template>
