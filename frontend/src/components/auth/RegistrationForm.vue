<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui'
import type { AuthForm } from '@/features/auth/model/types'

const userStore = useUserStore()
const router = useRouter()
const message = useMessage()

const form = ref<AuthForm>({
  email: '',
  username: '',
  password: '',
  confirmPassword: ''
})

const handleSignup = () => {
  const result = userStore.signup(form.value)
  if (result.success) {
    router.push('/vaults')
  } else {
    message.error(result.message || 'Registration failed')
  }
}
</script>

<template>
  <NForm>
    <NFormItem label="EMAIL">
      <NInput v-model:value="form.email" placeholder="ENTER EMAIL" />
    </NFormItem>
    <NFormItem label="USERNAME">
      <NInput v-model:value="form.username" placeholder="ENTER USERNAME" />
    </NFormItem>
    <NFormItem label="PASSWORD">
      <NInput v-model:value="form.password" type="password" placeholder="ENTER PASSWORD" />
    </NFormItem>
    <NFormItem label="CONFIRM PASSWORD">
      <NInput v-model:value="form.confirmPassword" type="password" placeholder="CONFIRM PASSWORD" />
    </NFormItem>
    <NButton type="primary" block @click="handleSignup"> INITIALIZE REGISTRATION</NButton>
  </NForm>
</template>

<style scoped></style>
