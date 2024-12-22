<script setup lang="ts">
import { ref } from 'vue';
import { NTabs, NTabPane } from 'naive-ui';
import LoginForm from './LoginForm.vue';
import SignupForm from './SignupForm.vue';

const activeTab = ref('login');
</script>

<template>
  <NTabs v-model:value="activeTab" type="segment" class="auth-tabs">
    <NTabPane name="login" tab="LOGIN">
      <LoginForm />
    </NTabPane>

    <NTabPane name="signup" tab="SIGN UP">
      <SignupForm />
    </NTabPane>
  </NTabs>
</template>

<style scoped>
.auth-tabs {
  margin-top: 20px;
}

:deep(.n-tabs-nav) {
  border: 1px solid var(--theme-border) !important;
}

:deep(.n-tabs-tab) {
  color: var(--theme-text) !important;
}

:deep(.n-tabs-tab.n-tabs-tab--active) {
  background-color: var(--theme-primary) !important;
  color: var(--theme-background) !important;
}

:deep(.n-tabs-tab:hover) {
  color: var(--theme-hover) !important;
}
</style>
