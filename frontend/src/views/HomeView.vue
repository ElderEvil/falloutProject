<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <div class="home">
    <h1>Welcome to Fallout Shelter</h1>
    <p>You are logged in as: {{ authStore.user?.email }}</p>
  </div>
</template>

<style scoped>
h1 {
  font-size: 2rem;
  color: #00ff99;
}
</style>
