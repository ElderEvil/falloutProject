<script setup lang="ts">
import { ref } from 'vue'
import { NTabs, NTabPane } from 'naive-ui'
import LoginForm from '../../../../../../Downloads/project-bolt-sb1-hubjsk (4)/project/src/components/auth/LoginForm.vue'
import SignupForm from './SignupForm.vue'

const activeTab = ref('login')
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
  border: 1px solid #00ff00 !important;
}

:deep(.n-tabs-tab) {
  color: #00ff00 !important;
}

:deep(.n-tabs-tab.n-tabs-tab--active) {
  background-color: #00ff00 !important;
  color: #000000 !important;
}

:deep(.n-tabs-tab:hover) {
  color: #00cc00 !important;
}
</style>
