<script setup lang="ts">
import NavBar from '@/components/common/NavBar.vue'
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <NavBar />
    <!-- Main Content -->
    <main class="flex-grow">
      <router-view></router-view>
    </main>
  </div>
</template>

<style scoped></style>
