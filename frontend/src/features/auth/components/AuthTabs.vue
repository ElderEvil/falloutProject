<script setup lang="ts">
import { ref } from 'vue'
import { NTabs, NTabPane } from 'naive-ui'
import LoginForm from './LoginForm.vue'
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
</style>
