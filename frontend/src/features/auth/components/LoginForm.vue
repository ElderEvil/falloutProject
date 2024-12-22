<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../store/auth';
import { NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui';
import type { AuthForm } from '../model/types';

const authStore = useAuthStore();
const router = useRouter();
const message = useMessage();

const form = ref<AuthForm>({
  email: '',
  password: ''
});

const handleLogin = async () => {
  try {
    const result = await authStore.login(form.value);
    if (result.success) {
      router.push('/vaults');
    } else {
      message.error(result.message || 'Login failed');
    }
  } catch (error) {
    message.error('An error occurred during login');
  }
};
</script>

<template>
  <NForm>
    <NFormItem label="EMAIL">
      <NInput
        v-model:value="form.email"
        placeholder="ENTER EMAIL"
        @keyup.enter="handleLogin"
      />
    </NFormItem>
    <NFormItem label="PASSWORD">
      <NInput
        v-model:value="form.password"
        type="password"
        placeholder="ENTER PASSWORD"
        @keyup.enter="handleLogin"
      />
    </NFormItem>
    <NButton type="primary" block @click="handleLogin">
      INITIALIZE LOGIN SEQUENCE
    </NButton>
  </NForm>
</template>

<style scoped>
:deep(.n-form-item) {
  margin-bottom: 20px;
}

:deep(.n-form-item-label) {
  font-family: 'Courier New', Courier, monospace;
  color: var(--theme-text);
}

:deep(.n-button) {
  font-family: 'Courier New', Courier, monospace;
}
</style>
