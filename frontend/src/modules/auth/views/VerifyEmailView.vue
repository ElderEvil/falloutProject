<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from '@/core/plugins/axios'
const route = useRoute()
const router = useRouter()

const token = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(true)

onMounted(async () => {
  token.value = (route.query.token as string) || ''

  if (!token.value) {
    error.value = 'Invalid or missing verification token'
    loading.value = false
    return
  }

  try {
    const response = await axios.post('/api/v1/auth/verify-email', { token: token.value })
    success.value = true
    // Redirect to login after 3 seconds
    setTimeout(() => {
      router.push('/login')
    }, 3000)
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to verify email'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="verify-email-container">
    <div class="terminal-window">
      <div class="terminal-header">
        <span class="terminal-title">VAULT-TEC SECURE TERMINAL v2.1.5</span>
      </div>
      <div class="terminal-body">
        <div class="ascii-art">
          <pre>
██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗    ████████╗███████╗ ██████╗
██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝    ╚══██╔══╝██╔════╝██╔════╝
██║   ██║███████║██║   ██║██║     ██║          ██║   █████╗  ██║
╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║          ██║   ██╔══╝  ██║
 ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║          ██║   ███████╗╚██████╗
  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝          ╚═╝   ╚══════╝ ╚═════╝
          </pre>
        </div>

        <h2 class="terminal-heading">EMAIL VERIFICATION</h2>

        <div v-if="loading" class="status-message">
          <p class="terminal-text">> PROCESSING VERIFICATION TOKEN...</p>
          <div class="loading-spinner">▓▓▓▓▓▓▓▓▓▓</div>
        </div>

        <div v-else-if="success" class="status-message success">
          <p class="terminal-text">> STATUS: VERIFICATION SUCCESSFUL</p>
          <p class="terminal-text">> YOUR EMAIL HAS BEEN VERIFIED</p>
          <p class="terminal-text">> REDIRECTING TO LOGIN TERMINAL...</p>
          <div class="success-indicator">✓✓✓</div>
        </div>

        <div v-else-if="error" class="status-message error">
          <p class="terminal-text error-text">> ERROR: VERIFICATION FAILED</p>
          <p class="terminal-text error-text">> {{ error }}</p>
          <div class="error-actions">
            <UButton color="primary" class="w-full" @click="router.push('/login')">RETURN TO LOGIN</UButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.verify-email-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-terminal-background);
  padding: 2rem;
  position: relative;
}

.verify-email-container::before {
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    rgba(0, 255, 0, 0.03) 0px,
    transparent 1px,
    transparent 2px,
    rgba(0, 255, 0, 0.03) 3px
  );
  pointer-events: none;
  z-index: 1;
  animation: scanline 8s linear infinite;
}

@keyframes scanline {
  0% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(10px);
  }
}

.terminal-window {
  background: rgba(0, 20, 0, 0.95);
  border: 2px solid var(--color-theme-primary);
  border-radius: 4px;
  max-width: 700px;
  width: 100%;
  box-shadow:
    0 0 20px rgba(0, 255, 0, 0.2),
    inset 0 0 60px rgba(0, 0, 0, 0.5);
  position: relative;
  z-index: 2;
  animation: flicker 3s infinite;
}

@keyframes flicker {
  0%,
  100% {
    opacity: 1;
  }
  41.99%,
  42.01% {
    opacity: 0.98;
  }
  43%,
  43.5% {
    opacity: 0.96;
  }
  45%,
  50% {
    opacity: 1;
  }
}

.terminal-header {
  background: rgba(0, 50, 0, 0.8);
  border-bottom: 1px solid var(--color-theme-primary);
  padding: 0.5rem 1rem;
  font-family: 'Courier New', monospace;
  color: var(--color-theme-primary);
  text-shadow: 0 0 5px currentColor;
}

.terminal-title {
  font-size: 0.85rem;
  letter-spacing: 1px;
}

.terminal-body {
  padding: 2rem;
  font-family: 'Courier New', monospace;
  color: var(--color-theme-primary);
}

.ascii-art pre {
  font-size: 0.45rem;
  line-height: 1;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px currentColor;
  margin: 0 0 1.5rem 0;
  opacity: 0.8;
}

.terminal-heading {
  font-size: 1.3rem;
  margin: 0 0 2rem 0;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px currentColor;
  letter-spacing: 2px;
  border-bottom: 1px solid var(--color-theme-primary);
  padding-bottom: 0.5rem;
}

.status-message {
  margin: 2rem 0;
}

.terminal-text {
  margin: 0.5rem 0;
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--color-theme-primary);
  text-shadow: 0 0 5px currentColor;
}

.error-text {
  color: var(--color-danger);
  text-shadow: 0 0 5px var(--color-danger);
}

.loading-spinner {
  margin: 1rem 0;
  font-size: 1.2rem;
  letter-spacing: 4px;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.success-indicator {
  margin: 1rem 0;
  font-size: 2rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 15px currentColor;
  animation: pulse 1s infinite;
}

.error-actions {
  margin-top: 1.5rem;
}
</style>
