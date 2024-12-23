<script setup lang="ts">
import { ref } from 'vue'
import { NTabs, NTabPane } from 'naive-ui'
import LoginForm from '@/components/auth/LoginForm.vue'
import RegistrationForm from './RegistrationForm.vue'

const activeTab = ref('login')
</script>

<template>
  <NTabs v-model:value="activeTab" type="segment" class="auth-tabs">
    <NTabPane name="login" tab="LOGIN">
      <LoginForm />
    </NTabPane>

    <NTabPane name="register" tab="REGISTER">
      <RegistrationForm />
    </NTabPane>
  </NTabs>
</template>

<style scoped></style>
