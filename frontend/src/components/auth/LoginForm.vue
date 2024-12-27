<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui';
import type { AuthForm } from '@/types/auth';

const userStore = useUserStore();
const router = useRouter();
const message = useMessage();

const form = ref<AuthForm>({
  email: '',
  password: ''
});

const handleLogin = async () => {
  try {
    const result = await userStore.login(form.value);
    if (result.success) {
      await router.push('/vaults');
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
      <NInput v-model:value="form.email" placeholder="ENTER EMAIL" @keyup.enter="handleLogin" />
    </NFormItem>
    <NFormItem label="PASSWORD">
      <NInput
        v-model:value="form.password"
        type="password"
        placeholder="ENTER PASSWORD"
        @keyup.enter="handleLogin"
      />
    </NFormItem>
    <NButton type="primary" block @click="handleLogin"> INITIALIZE LOGIN SEQUENCE</NButton>
  </NForm>
</template>

<style scoped></style>
