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

function validate(): void {
  error.value = null
  if (!modelValue.value) {
    return
  }
  try {
    const parsed = parseInt(modelValue.value, 10)
    vaultNumberSchema.parse({ number: parsed })
  } catch (err: any) {
    error.value = err.errors?.[0]?.message || 'Invalid vault number'
  }
}

function isValid(): boolean {
  validate()
  return !error.value
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
    class="flex-grow"
  />
</template>
