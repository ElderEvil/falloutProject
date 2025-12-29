<script setup lang="ts">
/**
 * UDropdown - Terminal-themed dropdown menu
 *
 * Features:
 * - Click outside to close
 * - Keyboard navigation
 * - Position options
 */

interface Props {
  position?: 'left' | 'right'
}

const props = withDefaults(defineProps<Props>(), {
  position: 'right'
})

import { ref, onMounted, onUnmounted } from 'vue'

const isOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

const toggle = () => {
  isOpen.value = !isOpen.value
}

const close = () => {
  isOpen.value = false
}

const handleClickOutside = (event: MouseEvent) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    close()
  }
}

const handleEscape = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    close()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleEscape)
})

const positionClasses = {
  left: 'left-0',
  right: 'right-0'
}
</script>

<template>
  <div class="relative inline-block" ref="dropdownRef">
    <!-- Trigger -->
    <div @click="toggle">
      <slot name="trigger"></slot>
    </div>

    <!-- Dropdown Menu -->
    <Transition name="dropdown">
      <div
        v-if="isOpen"
        :class="[
          'absolute mt-2 w-48 z-dropdown',
          'bg-surface border-2 border-gray-800 rounded-lg shadow-glow-md',
          'py-2',
          positionClasses[position]
        ]"
      >
        <slot></slot>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
