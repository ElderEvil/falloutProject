<script setup lang="ts">
import { NCard } from 'naive-ui';
import AuthTabs from '@/components/auth/AuthTabs.vue';
</script>

<template>
  <div class="login-container">
    <NCard title="VAULT-TEC TERMINAL" class="login-card">
      <div class="terminal-header">
        ROBCO INDUSTRIES UNIFIED OPERATING SYSTEM
        <br />
        COPYRIGHT 2075-2077 ROBCO INDUSTRIES
      </div>
      <AuthTabs />
    </NCard>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 500px;
  border: 2px solid #00ff00;
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.3);
}

.terminal-header {
  font-family: 'Courier New', Courier, monospace;
  margin-bottom: 2em;
  text-align: center;
  line-height: 1.5;
}

:deep(.n-card-header) {
  text-align: center;
  font-size: 1.5em;
  font-weight: bold;
  letter-spacing: 2px;
}
</style>
