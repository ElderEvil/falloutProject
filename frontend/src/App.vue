<template>
  <div id="app">
    <nav v-if="authStore.isAuthenticated">
      <router-link to="/">Home</router-link>
      <button @click="logout">Logout</button>
    </nav>
    <router-view></router-view>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const logout = () => {
  authStore.logout()
  router.push('/login')
}
</script>
