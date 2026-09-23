<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import NavBar from './NavBar.vue'
import ExitRequestModal from '@/modules/dwellers/components/modals/ExitRequestModal.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'

defineProps<{
  isFlickering: boolean
  flickerOpacity?: number
}>()

const authStore = useAuthStore()
const isAuthenticated = computed(() => authStore.isAuthenticated)
const scanlinesEnabled = inject('scanlines', ref(true))
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <div v-if="scanlinesEnabled" class="scanlines" aria-hidden="true"></div>
    <NavBar />
    <main
      id="main-content"
      class="flex-grow pt-16"
      :class="{ flicker: isFlickering && flickerOpacity === undefined }"
      :style="flickerOpacity !== undefined ? { opacity: flickerOpacity } : {}"
      role="main"
    >
      <slot></slot>
    </main>
    <ExitRequestModal v-if="isAuthenticated" />
  </div>
</template>

<style scoped>
/* Add styles as needed */
</style>
