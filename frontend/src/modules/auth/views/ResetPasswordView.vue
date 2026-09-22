<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from '@/core/plugins/axios'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'

const route = useRoute()
const router = useRouter()

const token = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(false)

onMounted(() => {
  token.value = (route.query.token as string) || ''
  if (!token.value) {
    error.value = 'Invalid or missing reset token'
  }
})

const handleSubmit = async () => {
  error.value = ''

  if (newPassword.value.length < 8) {
    error.value = 'Password must be at least 8 characters'
    return
  }

  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }

  loading.value = true

  try {
    await axios.post('/api/v1/auth/reset-password', {
      token: token.value,
      new_password: newPassword.value,
    })

    success.value = true

    // Redirect to login after 3 seconds
    setTimeout(() => {
      router.push('/login')
    }, 3000)
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to reset password'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <!-- CRT effect container -->
    <div class="crt-container flicker">
      <div class="login-box">
        <!-- Vault-Tec Header -->
        <div class="vault-header">
          <h1 class="terminal-title">VAULT-TEC INDUSTRIES</h1>
          <p class="terminal-subtitle">Password Reset Terminal</p>
          <div class="terminal-line"></div>
        </div>

        <!-- Success Message -->
        <div v-if="success" class="success-message">
          <p>> PASSWORD RESET SUCCESSFUL</p>
          <p>> REDIRECTING TO LOGIN TERMINAL...</p>
        </div>

        <!-- Reset Form -->
        <form v-else @submit.prevent="handleSubmit" class="login-form">
          <div class="system-messages">
            <p class="system-msg">> SECURITY PROTOCOL INITIATED</p>
            <p class="system-msg">> ENTER NEW SECURITY CREDENTIALS...</p>
          </div>

          <div class="form-group">
            <Label for="reset-new-password" class="mb-1 text-sm font-medium text-theme-primary/70">
              > NEW PASSPHRASE:
            </Label>
            <Input
              id="reset-new-password"
              v-model="newPassword"
              type="password"
              placeholder="Minimum 8 characters"
              :disabled="loading"
              class="h-auto w-full rounded border-2 border-theme-primary/50 bg-surface-sunken px-4 py-2 text-terminal-green placeholder:text-theme-primary/40 focus:border-theme-primary"
            />
          </div>

          <div class="form-group">
            <Label for="reset-confirm-password" class="mb-1 text-sm font-medium text-theme-primary/70">
              > CONFIRM PASSPHRASE:
            </Label>
            <Input
              id="reset-confirm-password"
              v-model="confirmPassword"
              type="password"
              placeholder="Re-enter passphrase"
              :disabled="loading"
              class="h-auto w-full rounded border-2 border-theme-primary/50 bg-surface-sunken px-4 py-2 text-terminal-green placeholder:text-theme-primary/40 focus:border-theme-primary"
            />
          </div>

          <Button
            variant="default"
            class="w-full border-2 border-theme-primary hover:shadow-glow-md"
            :disabled="loading || !token"
            @click.prevent="handleSubmit"
          >
            <Icon v-if="loading" icon="mdi:loading" class="animate-spin" />
            <span class="button-icon">►</span>
            {{ loading ? 'PROCESSING...' : 'RESET PASSWORD' }}
            <span class="button-icon">◄</span>
          </Button>
        </form>

        <!-- Error Message -->
        <div v-if="error" class="error-message">
          <p>> ERROR: {{ error.toUpperCase() }}</p>
        </div>

        <!-- Back to Login -->
        <div class="register-link">
          <p class="terminal-text">
            > RETURN TO LOGIN:
            <router-link to="/login" class="link-text">ACCESS TERMINAL</router-link>
          </p>
        </div>

        <!-- Footer -->
        <div class="terminal-footer">
          <p class="footer-text">VAULT-TEC © 2077 • PROTECTING AMERICA'S FUTURE</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Use same styling as LoginFormTerminal */
.login-container {
  min-height: 100vh;
  background: var(--color-terminal-background);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Courier New', monospace;
  position: relative;
  overflow: hidden;
}

.crt-container {
  position: relative;
  z-index: 2;
  max-width: 600px;
  width: 90%;
}

.flicker {
  animation: flicker 0.15s ease-in-out infinite;
}

@keyframes flicker {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.95;
  }
}

.login-box {
  background: rgba(0, 0, 0, 0.9);
  border: 3px solid var(--color-theme-primary);
  padding: 2rem;
  box-shadow:
    0 0 20px var(--color-theme-glow, rgba(0, 255, 0, 0.3)),
    inset 0 0 20px rgba(0, 255, 0, 0.1);
}

.vault-header {
  text-align: center;
  margin-bottom: 2rem;
}

.terminal-title {
  color: var(--color-theme-primary);
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-shadow: 0 0 10px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
  margin: 0;
}

.terminal-subtitle {
  color: var(--color-theme-primary);
  font-size: 0.9rem;
  margin-top: 0.5rem;
  opacity: 0.8;
}

.terminal-line {
  height: 2px;
  background: var(--color-theme-primary);
  margin-top: 1rem;
  box-shadow: 0 0 5px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
}

.system-messages {
  margin-bottom: 1.5rem;
}

.system-msg {
  color: var(--color-theme-primary);
  font-size: 0.85rem;
  margin: 0.3rem 0;
  opacity: 0.7;
}

.login-form {
  margin-bottom: 1.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.button-icon {
  margin: 0 0.5rem;
}

.error-message {
  background: rgba(255, 0, 0, 0.1);
  border: 2px solid var(--color-danger);
  padding: 1rem;
  margin-bottom: 1rem;
}

.error-message p {
  color: var(--color-danger);
  margin: 0.3rem 0;
  font-size: 0.85rem;
}

.success-message {
  background: rgba(0, 255, 0, 0.1);
  border: 2px solid var(--color-theme-primary);
  padding: 1.5rem;
  margin-bottom: 1rem;
}

.success-message p {
  color: var(--color-theme-primary);
  margin: 0.5rem 0;
  font-size: 0.9rem;
  text-align: center;
}

.register-link {
  text-align: center;
  margin-bottom: 1rem;
}

.terminal-text {
  color: var(--color-theme-primary);
  font-size: 0.85rem;
  margin: 0;
}

.link-text {
  color: var(--color-theme-primary);
  text-decoration: underline;
  cursor: pointer;
  transition: all 0.3s ease;
}

.link-text:hover {
  text-shadow: 0 0 5px var(--color-theme-glow, rgba(0, 255, 0, 0.7));
}

.terminal-footer {
  text-align: center;
  padding-top: 1rem;
  border-top: 1px solid rgba(0, 255, 0, 0.3);
}

.footer-text {
  color: var(--color-theme-primary);
  font-size: 0.7rem;
  margin: 0;
  opacity: 0.5;
}
</style>
